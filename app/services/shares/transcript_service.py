import asyncio

from fastapi import HTTPException
from youtube_transcript_api import YouTubeTranscriptApi


class YoutubeTranscriptService:
    """Service xử lý lấy phụ đề (transcript) từ video YouTube."""

    async def fetch_transcript(self, video_id: str, lang_priority=("vi", "en")):
        """Lấy phụ đề gốc từ YouTube."""
        try:
            # chạy trong thread để không block event loop
            transcript = await asyncio.to_thread(
                lambda: YouTubeTranscriptApi().fetch(video_id, languages=lang_priority)
            )
            return transcript
        except Exception as e:
            raise HTTPException(500, detail=f"Không lấy được phụ đề: {e}")

    @staticmethod
    def format_transcript_markdown(transcript) -> str:
        """Chuyển transcript (FetchedTranscript) sang Markdown có timestamp."""
        markdown_lines = []
        for item in transcript:
            start_time = int(item.start)
            minutes, seconds = divmod(start_time, 60)
            timestamp = f"{minutes:02d}:{seconds:02d}"
            text = item.text.strip().replace("\n", " ")
            markdown_lines.append(f"- `{timestamp}` {text}")
        return "\n".join(markdown_lines)

    async def extract_video_context(self, video_id: str) -> str:
        """Lấy phụ đề và định dạng Markdown — phục vụ hệ thống RAG."""
        transcript = await self.fetch_transcript(video_id)
        markdown = self.format_transcript_markdown(transcript)
        if not markdown:
            raise HTTPException(404, detail="❌ Không tìm thấy phụ đề cho video này.")
        return markdown
