from pypdf import PdfReader
from io import BytesIO


def extract_pdf_text(file_object):
    try:
        reader = PdfReader(file_object)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"PDF extraction error: {str(e)}\n{error_details}")
        raise Exception(f"Error extracting PDF text: {str(e)}")
