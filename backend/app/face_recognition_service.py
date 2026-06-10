import os, cv2, numpy as np

class SimpleFaceMatcher:
    """Lightweight face-name matcher without heavy dependencies.
    It uses Haar face detection and color histograms as a demo-friendly baseline.
    Replace with face_recognition/DeepFace for production accuracy.
    """
    def __init__(self, root="known_faces"):
        self.root = root
        os.makedirs(root, exist_ok=True)
        self.detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self.embeddings = []
        self.reload()

    def _face_crop(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = self.detector.detectMultiScale(gray, 1.2, 5)
        if len(faces) == 0:
            return None
        x,y,w,h = max(faces, key=lambda f: f[2]*f[3])
        return img[y:y+h, x:x+w]

    def _vector(self, crop):
        crop = cv2.resize(crop, (96, 96))
        hist = cv2.calcHist([crop], [0,1,2], None, [8,8,8], [0,256,0,256,0,256])
        cv2.normalize(hist, hist)
        return hist.flatten()

    def reload(self):
        self.embeddings.clear()
        for name in os.listdir(self.root):
            pdir = os.path.join(self.root, name)
            if not os.path.isdir(pdir):
                continue
            for fn in os.listdir(pdir):
                if fn.lower().endswith((".jpg", ".jpeg", ".png")):
                    img = cv2.imread(os.path.join(pdir, fn))
                    if img is None: continue
                    crop = self._face_crop(img) or img
                    self.embeddings.append((name, self._vector(crop)))

    def match(self, frame):
        if not self.embeddings:
            return "Unknown", 0.0
        crop = self._face_crop(frame)
        if crop is None:
            return "Unknown", 0.0
        vec = self._vector(crop)
        best_name, best_score = "Unknown", -1
        for name, emb in self.embeddings:
            score = cv2.compareHist(vec.astype('float32'), emb.astype('float32'), cv2.HISTCMP_CORREL)
            if score > best_score:
                best_name, best_score = name, score
        if best_score < 0.45:
            return "Unknown", float(best_score)
        return best_name.replace("_", " "), float(best_score)

face_matcher = SimpleFaceMatcher()
