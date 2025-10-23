import io
import base64
import json
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class CVUploadLine(models.TransientModel):
    _name = "advanced_recruitment.cv_upload_line"
    _description = "Temporary CV Upload"

    wizard_id = fields.Many2one("advanced_recruitment.cv_scan_wizard")
    filename = fields.Char("Filename")
    file = fields.Binary("File", required=True)

    @api.onchange('file')
    def _onchange_file(self):
        if self.file and not self.filename:
            self.filename = "uploaded_cv.pdf"


class CVScanWizard(models.TransientModel):
    _name = "advanced_recruitment.cv_scan_wizard"
    _description = "Scan CVs Wizard"

    job_description = fields.Text("Job Description", required=True)
    top_n = fields.Integer("Number of Top CVs", required=True, default=3)
    upload_lines = fields.One2many("advanced_recruitment.cv_upload_line", "wizard_id", string="CV Files")

    def _extract_text(self, data, filename):
        """Extract text from PDF or DOCX files"""
        text = ""
        try:
            if filename.lower().endswith(".pdf"):
                # Try using fitz (PyMuPDF)
                try:
                    import fitz
                    pdf_document = fitz.open(stream=data, filetype="pdf")
                    for page_num in range(len(pdf_document)):
                        page = pdf_document.load_page(page_num)
                        text += page.get_text()
                    pdf_document.close()
                except ImportError:
                    # Fallback to PyPDF2
                    from PyPDF2 import PdfReader
                    reader = PdfReader(io.BytesIO(data))
                    for page in reader.pages:
                        text += page.extract_text() or ""

            elif filename.lower().endswith(".docx"):
                # Try using python-docx
                try:
                    from docx import Document
                    doc = Document(io.BytesIO(data))
                    text = "\n".join([paragraph.text for paragraph in doc.paragraphs if paragraph.text])
                except ImportError:
                    text = "DOCX processing not available"

            else:
                text = data.decode('utf-8', errors='ignore')

        except Exception as e:
            _logger.error(f"Text extraction error: {str(e)}")
            text = f"Error extracting text: {str(e)}"

        return text.strip()

    def _extract_basic_info(self, text):
        """Extract name, email, and phone from text"""
        # Email extraction
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        email = emails[0] if emails else "No email found"

        # Phone extraction
        phone_pattern = r'[\+\(]?[1-9][0-9 .\-\(\)]{8,}[0-9]'
        phones = re.findall(phone_pattern, text)
        phone = phones[0] if phones else "No phone found"

        # Name extraction
        lines = text.split('\n')
        name = "Candidate"
        for line in lines[:5]:
            line = line.strip()
            if (len(line.split()) >= 2 and len(line.split()) <= 4 and
                    any(char.isalpha() for char in line) and
                    not line.lower().startswith(('email', 'phone', 'mobile', 'curriculum', 'vitae'))):
                name = line
                break

        return name, email, phone

    def _get_gemini_match_score(self, job_description, cv_text):
        """Simple and smart analysis - Gemini will handle everything automatically"""
        try:
            import requests

            GEMINI_API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxx"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

            prompt = f"""
            Analyze job-CV match and return score 0-100.

            Job: {job_description}
            CV: {cv_text}

            Consider: skills match, experience, projects, relevance.
            Return JSON: {{"match_score": 75, "reason": "brief explanation"}}
            """

            headers = {'Content-Type': 'application/json'}
            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }]
            }

            _logger.info("🔍 Calling Simple Gemini Analysis...")
            response = requests.post(url, headers=headers, json=data, timeout=30)
            _logger.info(f"🔍 Gemini API Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    text_response = result['candidates'][0]['content']['parts'][0]['text']
                    _logger.info(f"🔍 Gemini Response: {text_response}")

                    # Simple score extraction - any number between 0-100
                    import re
                    numbers = re.findall(r'\b([0-9]{1,2}0?)\b', text_response)
                    for num in numbers:
                        score = int(num)
                        if 0 <= score <= 100:
                            reason = "Gemini analysis completed"
                            _logger.info(f"✅ Extracted Score: {score}%")
                            return score, reason

            # If no score found, use simple fallback
            return self._calculate_simple_fallback(job_description, cv_text)

        except Exception as e:
            _logger.error(f"❌ Gemini Exception: {str(e)}")
            return self._calculate_simple_fallback(job_description, cv_text)

    def _calculate_simple_fallback(self, job_description, cv_text):
        """Simple fallback - basic word matching"""
        job_words = set(job_description.lower().split())
        cv_words = set(cv_text.lower().split())

        common_words = job_words.intersection(cv_words)

        if job_words:
            match_ratio = len(common_words) / len(job_words)
            score = 30 + (match_ratio * 50)  # 30-80 range
            score = min(max(score, 30), 80)
            reason = f"Basic matching: {len(common_words)} common terms"
            _logger.info(f"🔧 Fallback Score: {score}%")
            return score, reason

        return 50, "Neutral match"

    def _extract_json_from_response(self, text_response):
        """Extract JSON from Gemini response with multiple methods"""
        try:
            # Method 1: Direct JSON parsing
            try:
                return json.loads(text_response.strip())
            except:
                pass

            # Method 2: Extract JSON between curly braces
            start_idx = text_response.find('{')
            end_idx = text_response.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                json_str = text_response[start_idx:end_idx]
                return json.loads(json_str)

            # Method 3: Find JSON with regex
            import re
            json_match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}|\{[^{}]*\}', text_response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

            return None
        except Exception as e:
            _logger.error(f"JSON extraction failed: {e}")
            return None

    def action_generate_top(self):
        """Main function to process CVs and return top matches"""
        Resume = self.env["advanced_recruitment.resume"]
        Resume.search([]).unlink()

        job_text = self.job_description.strip()
        if not job_text:
            raise UserError("Please enter a job description")

        if not self.upload_lines:
            raise UserError("Please upload at least one CV")

        cv_records = []
        processed_count = 0

        _logger.info(f"🔍 Starting to process {len(self.upload_lines)} CVs")

        for idx, line in enumerate(self.upload_lines):
            if not line.file:
                continue

            try:
                _logger.info(f"🔍 Processing CV {idx + 1}: {line.filename}")

                file_data = base64.b64decode(line.file)
                filename = line.filename or "uploaded_cv.pdf"

                # Extract text
                cv_text = self._extract_text(file_data, filename)
                _logger.info(f"🔍 Extracted text length: {len(cv_text)}")

                if not cv_text or len(cv_text.strip()) < 10:
                    _logger.warning(f"⚠️ Skipping {filename} - no text extracted")
                    continue

                name, email, phone = self._extract_basic_info(cv_text)
                _logger.info(f"🔍 Basic Info: {name}, {email}")

                # Get Gemini score
                score, match_reason = self._get_gemini_match_score(job_text, cv_text)
                _logger.info(f"🎯 Final Score for {name}: {score}% - {match_reason}")

                # Create record
                rec = Resume.create({
                    "candidate_name": name,
                    "email": email,
                    "phone": phone,
                    "source_filename": filename,
                    "raw_text": f"AI Analysis: {match_reason}\n\nExtracted Text: {cv_text[:800]}...",
                    "cv_file": line.file,
                    "score": score
                })

                cv_records.append(rec)
                processed_count += 1
                _logger.info(f"✅ Successfully processed: {name}")

            except Exception as e:
                _logger.error(f"❌ Error processing {line.filename}: {str(e)}")
                continue

        _logger.info(f"🔍 Completed processing. Total CVs processed: {processed_count}")

        if not cv_records:
            raise UserError("No valid CVs could be processed. Please check your files and try again.")

        top_records = sorted(cv_records, key=lambda r: r.score, reverse=True)[:self.top_n]

        return {
            "type": "ir.actions.act_window",
            "name": f"Top {len(top_records)} CVs (Processed: {processed_count})",
            "res_model": "advanced_recruitment.resume",
            "view_mode": "list,form",
            "domain": [("id", "in", [r.id for r in top_records])],
            "target": "current",
        }