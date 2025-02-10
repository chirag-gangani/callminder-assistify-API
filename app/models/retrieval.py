from dataclasses import dataclass
from typing import List

@dataclass
class RetrievalResult:
    chunks: List[str]
    similarities: List[float]
    sources: List[str]
    page_numbers: List[int]
    
    def __init__(self):
        self.chunks = []
        self.similarities = []
        self.sources = []
        self.page_numbers = []

    @staticmethod
    def empty():
        result = RetrievalResult()
        result.chunks = []
        result.similarities = []
        result.sources = []
        result.page_numbers = []
        return result