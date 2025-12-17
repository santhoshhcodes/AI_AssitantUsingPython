# ai_agent/employee_store.py
import faiss
import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
INDEX_FILE = "data/employee.index"
META_FILE = "data/employee_meta.json"

model = SentenceTransformer(MODEL_NAME)
VECTOR_DIM = model.get_sentence_embedding_dimension()


class EmployeeVectorStore:
    def __init__(self):
        self.index = None
        self.meta = []
        self._load()

    def _load(self):
        if os.path.exists(INDEX_FILE) and os.path.exists(META_FILE):
            self.index = faiss.read_index(INDEX_FILE)
            with open(META_FILE, "r") as f:
                self.meta = json.load(f)
        else:
            self.index = faiss.IndexFlatL2(VECTOR_DIM)
            self.meta = []

    def build(self, employees: list):
        self.index = faiss.IndexFlatL2(VECTOR_DIM)
        self.meta = []

        texts = []
        for emp in employees:
            text = (
                f"Employee {emp['FirstName']}, "
                 f"EmpNo {emp['EmpNo']} "
                f"Designation {emp['Designation']}, "
                f"Department {emp['DeptName']}, "
                f"Mobile {emp['EmployeeMobile']}"
            )
            texts.append(text)
            self.meta.append(emp)

        vectors = model.encode(texts, show_progress_bar=True)
        self.index.add(np.array(vectors).astype("float32"))

        os.makedirs("data", exist_ok=True)
        faiss.write_index(self.index, INDEX_FILE)

        with open(META_FILE, "w") as f:
            json.dump(self.meta, f)

    def search(self, query: str, top_k=5):
        try:
            if not query or self.index.ntotal == 0:
                return []

            q_vec = model.encode([query]).astype("float32")
            distances, indices = self.index.search(q_vec, top_k)

            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx < 0 or idx >= len(self.meta):
                    continue
                emp = self.meta[idx].copy()
                emp["_score"] = float(dist)
                results.append(emp)
            
            return results
        except Exception as e:
            print(f"Vector search error: {e}")
            return []
