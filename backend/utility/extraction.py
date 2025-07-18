import openai
import os
import pdfplumber
import io

# # Extract triplets from text using OpenAI
# def extract_triplets_from_text(text):
#     prompt = (
#         "Extract (subject, relation, object) triplets from the following text. "
#         "Return as a JSON list of objects with keys: subject, relation, object.\n\n"
#         f"Text:\n{text}\n\nTriplets:"
#     )
#     openai.api_key = os.getenv("OPENAI_API_KEY")
#     response = openai.chat.completions.create(
#         model="gpt-4.1-nano",
#         messages=[{"role": "user", "content": prompt}],
#         max_tokens=512,
#         temperature=0.0,
#     )
#     content = response.choices[0].message.content


# Extract text from a PDF file (UploadFile)
def extract_text_from_pdf(upload_file):
    with pdfplumber.open(io.BytesIO(upload_file.file.read())) as pdf:
        all_text = "\n\n".join(
            page.extract_text() or "" for page in pdf.pages
        ).strip()
    return all_text



# Extract context from CSV records (limit to first 10 rows)
def extract_context_from_csv_records(records):
    context_rows = [str(r.row_data) for r in records[:10]]
    return "\n".join(context_rows)