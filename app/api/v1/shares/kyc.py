# # app/api/v1/kyc_video_router.py
# import os
# import shutil
# import tempfile

# from fastapi import APIRouter, File, UploadFile

# router = APIRouter(prefix="/kyc", tags=["KYC"])


# @router.post("/verify-video")
# async def verify_video(
#     selfie_video: UploadFile = File(..., description="Video selfie 3–7s (mp4/webm)")
# ):
#     tmp_dir = tempfile.mkdtemp(prefix="kyc_")
#     try:
#         video_path = os.path.join(tmp_dir, "selfie.mp4")
#         with open(video_path, "wb") as f:
#             shutil.copyfileobj(selfie_video.file, f)

#         result = SimpleLiveness().analyze(video_path, max_seconds=7)
#         if not result["passed"]:
#             return {"verified": False, "liveness": result}

#         return {"verified": True, "liveness": result}
#     finally:
#         # Xoá hoặc giữ lại để debug tuỳ bạn
#         # shutil.rmtree(tmp_dir, ignore_errors=True)
#         pass
