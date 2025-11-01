# app/services/lecturer/lesson_service.py
import uuid
from io import BytesIO

from fastapi import BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.embedding import EmbeddingService
from app.db.models.database import (
    Courses,
    CourseSections,
    LessonChunks,
    Lessons,
    LessonVideos,
    User,
)
from app.db.sesson import AsyncSessionLocal, get_session
from app.schemas.lecturer.lesson import CreateLesson
from app.services.shares.google_driver import GoogleDriveService
from app.services.shares.youtube_uploader import YouTubeUploader


class LessonService:

    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        google_drive: GoogleDriveService = Depends(GoogleDriveService),
        embedding: EmbeddingService = Depends(EmbeddingService),
        youtube: YouTubeUploader = Depends(YouTubeUploader),
    ):
        self.db = db
        self.google_drive = google_drive
        self.embedding = embedding
        self.youtube = youtube

    # 🧩 Tạo bài học (lesson)
    async def create_lesson_async(self, schema: CreateLesson, lecturer: User):
        try:
            section = await self.db.scalar(
                select(CourseSections).where(CourseSections.id == schema.section_id)
            )
            if not section:
                raise HTTPException(
                    404, f"Không tìm thấy chương học {schema.section_id}"
                )

            course = await self.db.scalar(
                select(Courses).where(
                    Courses.id == section.course_id,
                    Courses.instructor_id == lecturer.id,
                )
            )
            if not course:
                raise HTTPException(
                    403, "Bạn không có quyền tạo bài học trong khóa học này"
                )

            last_lesson = await self.db.scalar(
                select(Lessons)
                .where(Lessons.section_id == section.id)
                .order_by(desc(Lessons.position))
            )

            new_lesson = Lessons(**schema.model_dump())
            new_lesson.position = (last_lesson.position + 1) if last_lesson else 0
            self.db.add(new_lesson)
            await self.db.commit()
            await self.db.refresh(new_lesson)
            return {"message": "Tạo bài học thành công", "id": new_lesson.id}
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"Lỗi khi tạo bài học: {e}")

    # app/services/lesson_service.py

    # 🎥 Upload video lên YouTube cho bài học
    async def upload_video_async(
        self,
        video: UploadFile,
        lecturer,
        lesson_id: uuid.UUID,
        background_tasks: BackgroundTasks,
    ):
        try:
            # 🔍 1. Kiểm tra trùng video
            existing = await self.db.scalar(
                select(LessonVideos).where(LessonVideos.lesson_id == lesson_id)
            )
            if existing:
                raise HTTPException(409, "Video đã tồn tại cho bài học này")

            # 🔍 2. Kiểm tra bài học & quyền giảng viên
            lesson = await self.db.scalar(
                select(Lessons)
                .options(selectinload(Lessons.section))
                .where(Lessons.id == lesson_id)
            )
            if not lesson:
                raise HTTPException(404, "Không tồn tại bài học")

            section = lesson.section
            course = await self.db.scalar(
                select(Courses).where(Courses.id == section.course_id)
            )
            if not course or course.instructor_id != lecturer.id:
                raise HTTPException(403, "Bạn không có quyền truy cập khóa học này")

            # 🚀 3. Upload trực tiếp lên YouTube (không ghi file tạm)
            content = await video.read()
            stream = BytesIO(content)
            result = await self._upload_to_youtube_stream(
                stream,
                title=f"{course.title} - {lesson.title}",
                description=f"Khóa học {course.title} - Bài học: {lesson.title}",
            )

            video_id = result["video_id"]
            video_url = result["video_url"]
            duration_seconds = result["duration_seconds"]

            # 🧩 4. Lưu metadata video
            lesson_video = LessonVideos(
                lesson_id=lesson.id,
                provider="youtube",
                file_id=video_id,
                video_url=video_url,
                duration=duration_seconds or 0.0,
                transcript="",
            )
            self.db.add(lesson_video)
            await self.db.commit()
            await self.db.refresh(lesson_video)

            # 🧠 5. Gọi AI xử lý mô tả video
            background_tasks.add_task(
                LessonService.process_video_description_async, lesson_id, video_url
            )

            return {
                "message": "✅ Video đã tải lên YouTube và đang xử lý AI.",
                "provider": "youtube",
                "video_url": video_url,
                "duration_seconds": duration_seconds,
            }

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, f"❌ Lỗi khi tải video lên YouTube: {e}")

    async def _upload_to_youtube_stream(
        self, stream: BytesIO, title: str, description: str
    ):
        """Upload YouTube trực tiếp từ BytesIO (không ghi file tạm)"""
        from googleapiclient.http import MediaIoBaseUpload

        media = MediaIoBaseUpload(stream, mimetype="video/mp4", resumable=True)
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": "27",  # Education
            },
            "status": {"privacyStatus": "unlisted"},
        }

        def _sync_upload():
            request = self.youtube.service.videos().insert(
                part="snippet,status", body=body, media_body=media
            )
            response = request.execute()
            video_id = response.get("id")
            duration = self.youtube.get_duration(video_id)
            return {
                "video_id": video_id,
                "video_url": self.youtube.get_video_url(video_id),
                "duration_seconds": duration,
            }

        # chạy trong thread pool (YouTube API là blocking)
        import asyncio

        return await asyncio.to_thread(_sync_upload)

    # 🧠 Xử lý mô tả video (AI embedding)
    @staticmethod
    async def process_video_description_async(
        lesson_id: uuid.UUID,
        link: str,
        embedding: EmbeddingService = Depends(EmbeddingService),
    ):
        async with AsyncSessionLocal() as db:
            try:
                # 🧠 1. Trích ngữ cảnh từ video
                description = await embedding.extract_video_context_from_url(link)
                print("🧠 Gemini mô tả:", description[:200], "...")

                total_tokens = embedding.estimate_tokens(description)
                lesson_embedding = await embedding.embed_google_3072(description)
                chunks = embedding.split_text_by_tokens(description, max_tokens=1000)

                # 🧱 2. Cập nhật embedding + transcript
                await db.execute(
                    update(Lessons)
                    .where(Lessons.id == lesson_id)
                    .values(
                        embedding=lesson_embedding,
                        content_tokens=total_tokens,
                    )
                )
                await db.execute(
                    update(LessonVideos)
                    .where(LessonVideos.lesson_id == lesson_id)
                    .values(transcript=description)
                )

                # 🧩 3. Chia nhỏ nội dung cho RAG
                lesson_chunks = []
                for idx, chunk_text in enumerate(chunks):
                    chunk_embed = await embedding.embed_google_3072(chunk_text)
                    lesson_chunks.append(
                        LessonChunks(
                            lesson_id=lesson_id,
                            chunk_index=idx,
                            text_=chunk_text,
                            embedding=chunk_embed,
                            token_count=embedding.estimate_tokens(chunk_text),
                        )
                    )
                db.add_all(lesson_chunks)
                await db.commit()

                print(
                    f"✅ [{lesson_id}] xử lý xong ({len(chunks)} chunks, {total_tokens} tokens)"
                )

            except Exception as e:
                await db.rollback()
                import traceback

                traceback.print_exc()
                print(f"❌ Lỗi khi xử lý bài học {lesson_id}: {e}")
