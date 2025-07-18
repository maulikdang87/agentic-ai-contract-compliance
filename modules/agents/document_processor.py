import PyPDF2
import docx
from typing import List, Dict, Optional
import re
from pathlib import Path

class DocumentProcessor:
    def __init__(self):
        self.supported_formats = ['.pdf', '.docx', '.txt']
         
    def extract_text(self, file_path: str) -> str:
        """Extract text from various document formats"""
        file_path = Path(file_path)
        
        if file_path.suffix.lower() == '.pdf':
            return self._extract_from_pdf(file_path)
        elif file_path.suffix.lower() == '.docx':
            return self._extract_from_docx(file_path)
        elif file_path.suffix.lower() == '.txt':
            return self._extract_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
    
    def _extract_from_pdf(self, file_path: Path) -> str:
        """Extract text from PDF files"""
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    
    def _extract_from_docx(self, file_path: Path) -> str:
        """Extract text from Word documents"""
        doc = docx.Document(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    
    def _extract_from_txt(self, file_path: Path) -> str:
        """Extract text from plain text files"""
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    
    def chunk_document(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        """Split document into overlapping chunks"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            chunks.append(chunk)
            
            if i + chunk_size >= len(words):
                break
        
        return chunks
    
    def extract_metadata(self, text: str) -> Dict:
        """Extract basic metadata from contract text"""
        metadata = {
            'word_count': len(text.split()),
            'char_count': len(text),
            'parties': self._extract_parties(text),
            'dates': self._extract_dates(text),
            'contract_type': self._identify_contract_type(text)
        }
        return metadata
    
    def _extract_parties(self, text: str) -> List[str]:
        """Extract party names from contract"""
        # Simple regex patterns for common party indicators
        patterns = [
            r'between\s+([A-Z][a-zA-Z\s&,\.]+?)\s+and\s+([A-Z][a-zA-Z\s&,\.]+?)(?:\s|,|\.|;)',
            r'Party\s+(?:A|1):\s*([A-Z][a-zA-Z\s&,\.]+?)(?:\n|Party)',
            r'Party\s+(?:B|2):\s*([A-Z][a-zA-Z\s&,\.]+?)(?:\n|Party)'
        ]
        
        parties = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            parties.extend([match if isinstance(match, str) else match[0] for match in matches])
        
        return list(set(parties))[:5]  # Limit to 5 parties
    
    def _extract_dates(self, text: str) -> List[str]:
        """Extract dates from contract"""
        date_patterns = [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
        ]
        
        dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            dates.extend(matches)
        
        return list(set(dates))[:10]  # Limit to 10 dates
    
    def _identify_contract_type(self, text: str) -> str:
        """Identify the type of contract"""
        contract_types = {
            'employment': ['employment', 'employee', 'salary', 'benefits', 'termination'],
            'service': ['services', 'provider', 'client', 'deliverables', 'scope of work'],
            'sales': ['purchase', 'sale', 'buyer', 'seller', 'goods', 'products'],
            'lease': ['lease', 'rent', 'tenant', 'landlord', 'property'],
            'nda': ['confidential', 'non-disclosure', 'proprietary', 'confidentiality']
        }
        
        text_lower = text.lower()
        scores = {}
        
        for contract_type, keywords in contract_types.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            scores[contract_type] = score
        
        return max(scores, key=scores.get) if max(scores.values()) > 0 else 'general'

