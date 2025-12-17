import faiss
import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
INDEX_FILE = "data/employee.index"
META_FILE = "data/employee_meta.json"

model = SentenceTransformer(MODEL_NAME)

class EmployeeVectorStore:
    def __init__(self):
        self.index = None
        self.meta = []
        self._load()

    def _load(self):
        if os.path.exists(INDEX_FILE):
            self.index = faiss.read_index(INDEX_FILE)
            with open(META_FILE, "r") as f:
                self.meta = json.load(f)
        else:
            self.index = faiss.IndexFlatL2(384)

    def build(self, employees: list):
        self.index = faiss.IndexFlatL2(384)
        self.meta = []

        texts = []
        for emp in employees:
            text = f"""
            Empno {emp['EmpNo']}
            Employee {emp['FirstName']}
            Designation {emp['Designation']}
            Department {emp['DeptName']}
            Mobile {emp['EmployeeMobile']}
            """
            texts.append(text)
            self.meta.append(emp)

        vectors = model.encode(texts)
        self.index.add(np.array(vectors).astype("float32"))

        os.makedirs("data", exist_ok=True)
        faiss.write_index(self.index, INDEX_FILE)

        with open(META_FILE, "w") as f:
            json.dump(self.meta, f)

def search(self, query: str, top_k=5, max_distance=0.75):
    if self.index.ntotal == 0:
        return []

    q_vec = model.encode([query]).astype("float32")
    distances, indices = self.index.search(q_vec, top_k)

    results = []

    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0 or idx >= len(self.meta):
            continue
        if dist > max_distance:
            continue

        emp = self.meta[idx].copy()
        emp["_score"] = float(dist)
        results.append(emp)

    return results
