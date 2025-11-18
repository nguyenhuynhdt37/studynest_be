import json
import uuid
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.websockets import WebSocketState

from app.core.deps import AuthorizationService
from app.core.ws_manager import ws_manager
from app.schemas.auth.user import UserCreate
from app.schemas.lecturer.lesson import LessonCodeSaveFile, LessonCodeUserTest
from app.schemas.user.learning import (
    CreateLessonComment,
    CreateLessonNote,
    UpdateLessonComment,
    UpdateLessonNote,
)
from app.services.user.learning import LearningService

router = APIRouter(prefix="/learning", tags=["User Learning"])


@router.get("/{course_slug}")
async def get_course_enrolled(
    course_slug: str,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await learning_service.get_course_enrolled_async(course_slug, user)


@router.get("/{course_id}/instructor")
async def get_instructor_by_course_id(
    course_id: uuid.UUID,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await learning_service.get_instructor_by_course_id_async(course_id, user)


@router.get("/{course_id}/curriculum")
async def get_course_curriculum(
    course_id: uuid.UUID,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await learning_service.get_course_curriculum_async(course_id, user)


@router.get("/{course_id}/view/active")
async def get_lesson_active(
    course_id: uuid.UUID,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    lesson_type, lesson_id = (
        await learning_service.get_type_and_lesson_id_by_course_id_active(
            course_id, user
        )
    )
    match lesson_type:
        case "video":
            return await learning_service.get_lesson_video_async(lesson_id, user)
        case "quiz":
            return await learning_service.get_lesson_quiz_async(lesson_id, user)
        case "code":
            return await learning_service.get_lesson_code_async(lesson_id, user)
        case _:
            pass


@router.post("/{course_id}/active/{lesson_id}")
async def set_active_lesson(
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await learning_service.set_active_lesson_async(course_id, lesson_id, user)


@router.get("/{lesson_id}/check_prev_next")
async def get_prev_next_lesson(
    lesson_id: uuid.UUID,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await learning_service.get_prev_next_lesson_async(lesson_id, user)


@router.post("/{lesson_id}/next")
async def get_next_lesson_in_course(
    lesson_id: uuid.UUID,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await learning_service.get_next_lesson_in_course_async(lesson_id, user, True)


@router.post("/{lesson_id}/prev")
async def get_prev_lesson_in_course(
    lesson_id: uuid.UUID,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await learning_service.get_previous_lesson_in_course_async(lesson_id, user)


@router.post("/{lesson_id}/complete")
async def mark_lesson_completed(
    lesson_id: uuid.UUID,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await learning_service.mark_lesson_completed_async(lesson_id, user)


# @router.get("/{lesson_id}/lesson_comments")
# async def list_root_comments_with_reactions(
#     lesson_id: uuid.UUID,
#     limit: int = Query(10, ge=1, le=50),
#     cursor: Optional[str] = Query(None),
#     learning_service: LearningService = Depends(LearningService),
#     authorization: AuthorizationService = Depends(AuthorizationService),
# ):
#     await authorization.get_current_user()
#     return await learning_service.list_root_comments_with_reactions_async(
#         lesson_id, limit, cursor
#     )


@router.post("/{lesson_id}/lesson_comments")
async def create_lesson_comment(
    lesson_id: uuid.UUID,
    schema: CreateLessonComment,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    current_user = await authorization.get_current_user()
    return await learning_service.create_lesson_comment_async(
        lesson_id, schema, current_user
    )


@router.get("/code/language/{language_id}")
async def get_code_language_by_language_id(
    language_id: uuid.UUID,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    await authorization.get_current_user()
    return await learning_service.get_code_language_by_language_id_async(language_id)


@router.post("/code/{lesson_code_id}/save")
async def save_single_user_code(
    lesson_code_id: uuid.UUID,
    schema: LessonCodeSaveFile,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await learning_service.save_single_user_code_async(
        lesson_code_id=lesson_code_id, user=user, file_obj=schema
    )


@router.post("/code/{lesson_code_id}/test")
async def test_user_code(
    lesson_code_id: uuid.UUID,
    schema: LessonCodeUserTest,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await learning_service.test_user_code_async(schema, user, lesson_code_id)


@router.get("/code/{lesson_code_id}/starter_code")
async def get_lesson_start_code(
    lesson_code_id: uuid.UUID,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await learning_service.get_lesson_start_code_async(lesson_code_id, user)


@router.post("/lesson_note/{lesson_id}/create")
async def create_lesson_note(
    lesson_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    schema: CreateLessonNote,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await learning_service.create_lesson_note_async(
        lesson_id, schema, user.id, background_tasks
    )


@router.get("/{lesson_id}/lesson_notes")
async def get_user_notes(
    lesson_id: uuid.UUID,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await learning_service.get_notes_by_lesson_and_user_async(lesson_id, user.id)


@router.put("/lesson_notes/{note_id}")
async def update_note(
    note_id: uuid.UUID,
    schema: UpdateLessonNote,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    current_user = await authorization.get_current_user()
    return await learning_service.update_note_async(note_id, current_user.id, schema)


@router.delete("/lesson_notes/{note_id}")
async def delete_note(
    note_id: uuid.UUID,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    current_user = await authorization.get_current_user()
    return await learning_service.delete_note_async(note_id, current_user.id)


@router.get("/{lesson_id}/comments")
async def list_lesson_comments(
    lesson_id: uuid.UUID,
    root_id: Optional[uuid.UUID] = Query(
        None, description="ID của comment gốc (nếu depth > 0)"
    ),
    depth_target: int = Query(
        0, ge=0, le=2, description="0: root, 1: reply cấp 1, 2: thread sâu hơn"
    ),
    limit: int = Query(10, ge=1, le=50),
    cursor: Optional[str] = Query(None),
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    """
    📘 Lấy danh sách bình luận theo cấp độ (depth)
    - depth_target = 0 → comment gốc
    - depth_target = 1 → reply cấp 1 theo root_id
    - depth_target = 2 → toàn bộ thread sâu hơn theo root_id
    """
    user: UserCreate = await authorization.get_current_user()

    return await learning_service.get_lesson_comments_async(
        lesson_id=lesson_id,
        current_user_id=user.id,
        root_id=root_id,
        depth_target=depth_target,
        limit=limit,
        cursor=cursor,
    )


@router.get("/comments/{comment_id}/reacts")
async def get_list_react_by_comment(
    comment_id: uuid.UUID,
    learning_service: LearningService = Depends(LearningService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    """
    📘 Lấy danh sách reply cấp 1 của một bình luận gốc
    """
    await authorization.get_current_user()
    return await learning_service.get_list_react_by_comment_id(comment_id=comment_id)


@router.post("/comments/{comment_id}/reacts")
async def toggle_reaction(
    comment_id: uuid.UUID,
    auth: AuthorizationService = Depends(AuthorizationService),
    learning_service: LearningService = Depends(LearningService),
):
    """
    API HTTP: Thả hoặc bỏ thả tim cho bình luận (toggle).
    """
    user = await auth.get_current_user()
    return await learning_service.toggle_comment_reaction_async(comment_id, user.id)


@router.websocket("/ws/comments/{lesson_id}")
async def lesson_comment_ws(websocket: WebSocket, lesson_id: uuid.UUID):
    room_key = f"lesson_comment_ws_lesson_id_{lesson_id}"
    user = None

    async def send_safe(payload: dict):
        """Chỉ gửi nếu socket còn mở"""
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_json(payload)
            except Exception:
                pass  # socket đang đóng — bỏ qua an toàn

    async def disconnect_safe():
        """Ngắt kết nối WS và rời room an toàn"""
        try:
            ws_manager.disconnect(websocket, room_key)
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
        except Exception:
            pass

    try:
        await websocket.accept()

        user = await AuthorizationService.get_require_role_ws(websocket, ["USER"])
        if not user:
            return

        await ws_manager.connect(websocket, room_key)
        print(f"🟢 {user.email} joined {room_key}")

        while True:
            # nhận data client gửi lên
            try:
                raw = await websocket.receive_text()
                data = json.loads(raw)
                msg_type = data.get("type")
            except json.JSONDecodeError:
                await send_safe({"error": "Dữ liệu JSON không hợp lệ"})
                continue
            except WebSocketDisconnect:
                break  # client đóng kết nối
            except Exception as e:
                await send_safe({"error": f"Lỗi nhận dữ liệu: {e}"})
                continue

            # === TẠO COMMENT ===
            if msg_type == "create":
                try:
                    schema = CreateLessonComment(**(data.get("create") or data))
                    result = await LearningService.create_lesson_comment_async(
                        lesson_id, schema, user
                    )
                except Exception as e:
                    await send_safe({"error": f"Dữ liệu bình luận không hợp lệ: {e}"})
                    continue

                if not result or not result.get("type"):
                    await send_safe(
                        {"error": result.get("error", "Không tạo được bình luận")}
                    )
                    continue

                await ws_manager.broadcast(room_key, result)

            # === CẬP NHẬT COMMENT ===
            elif msg_type == "comment_update":
                payload = data.get("update") or data
                try:
                    comment_id = uuid.UUID(payload.get("id", ""))
                    schema = UpdateLessonComment(**payload)
                except ValueError:
                    await send_safe({"error": "ID bình luận không hợp lệ"})
                    continue
                except Exception as e:
                    await send_safe(
                        {"error": f"Dữ liệu cập nhật bình luận không hợp lệ: {e}"}
                    )
                    continue

                result = await LearningService.update_lesson_comment_async(
                    comment_id, schema, user
                )
                if not result or not result.get("type"):
                    await send_safe(
                        {"error": result.get("error", "Không cập nhật được bình luận")}
                    )
                    continue

                await ws_manager.broadcast(room_key, result)
            elif msg_type == "comment_delete":
                try:
                    comment_id = uuid.UUID(data.get("id", ""))
                except ValueError:
                    await send_safe({"error": "ID bình luận không hợp lệ"})
                    continue

                result = await LearningService.delete_lesson_comment_async(
                    comment_id, user.id
                )
                if not result or not result.get("type"):
                    await send_safe(
                        {"error": result.get("error", "Không xóa được bình luận")}
                    )
                    continue

                # Gửi realtime cho mọi client cùng phòng
                await ws_manager.broadcast(room_key, result)

            # === USER ĐANG GÕ ===
            elif msg_type == "typing":
                await ws_manager.broadcast(
                    room_key, {"type": "typing", "user_id": str(user.id)}
                )

            else:
                await send_safe({"error": f"Sự kiện '{msg_type}' không được hỗ trợ."})

    except WebSocketDisconnect:
        # client rời, không gửi thêm gì
        pass
    except Exception as e:
        await send_safe({"error": f"Lỗi hệ thống: {e}"})
    finally:
        await disconnect_safe()
        print(f"🔴 {user.email if user else 'Unknown'} left {room_key}")
