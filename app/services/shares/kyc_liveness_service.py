# app/services/kyc_video_face_service.py
import math

import cv2
import face_recognition
import mediapipe as mp
import numpy as np

mp_face_mesh = mp.solutions.face_mesh


class KYCVideoFaceService:
    def __init__(self):
        self.face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    @staticmethod
    def _lap_var(gray):
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    @staticmethod
    def _angle(v1, v2):
        v1 = v1 / (np.linalg.norm(v1) + 1e-9)
        v2 = v2 / (np.linalg.norm(v2) + 1e-9)
        return math.degrees(math.acos(np.clip(np.dot(v1, v2), -1.0, 1.0)))

    def _yaw_pitch(self, lms):
        try:
            nose = np.array(lms[1])
            mid_eyes = np.array(lms[168])
            chin = np.array(lms[152])
        except:
            return 0.0, 0.0
        yaw = self._angle(mid_eyes - nose, np.array([0, -1]))
        pitch = self._angle(chin - mid_eyes, np.array([0, 1]))
        return yaw, pitch

    def extract_best_frame(self, video_path: str):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None, "Không đọc được video."
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        max_frames = int(8 * fps)

        frames_meta = []
        used = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            used += 1
            if used > max_frames:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = self.face_mesh.process(rgb)
            if not res.multi_face_landmarks:
                continue

            lms = res.multi_face_landmarks[0].landmark
            pts = [(lm.x, lm.y) for lm in lms]
            yaw, pitch = self._yaw_pitch(pts)
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            face_ratio = (max(xs) - min(xs)) * (max(ys) - min(ys))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            texture = self._lap_var(gray)
            score = texture * face_ratio / (1 + yaw + pitch)
            frames_meta.append((score, frame.copy()))

        cap.release()
        if not frames_meta:
            return None, "Không phát hiện khuôn mặt nào."
        frames_meta.sort(key=lambda x: x[0], reverse=True)
        return frames_meta[0][1], None  # frame tốt nhất

    @staticmethod
    def compare_face(id_path: str, frame):
        try:
            id_img = face_recognition.load_image_file(id_path)
            selfie_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            id_enc = face_recognition.face_encodings(id_img)
            frame_enc = face_recognition.face_encodings(selfie_rgb)
            if not id_enc or not frame_enc:
                return False, 0.0
            dist = face_recognition.face_distance([id_enc[0]], frame_enc[0])[0]
            sim = 1 - dist
            return sim >= 0.75, round(float(sim), 3)
        except Exception:
            return False, 0.0
