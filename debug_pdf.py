"""Diagnostic: inspect PDF internals with PyPDF2 3.x."""
import io, sys, os, traceback
import PyPDF2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.extract_utils.extract_utils import preprocess_page_content, extract_graphics_string

BASE = os.path.dirname(os.path.abspath(__file__))

def inspect_pdf(path, label):
    print(f'\n===== {label} =====')
    print(f'Path: {path}')
    with open(path, 'rb') as f:
        data = f.read()
    reader = PyPDF2.PdfReader(io.BytesIO(data))
    print(f'Pages: {len(reader.pages)}')

    for p_idx in range(len(reader.pages)):
        page = reader.pages[p_idx]
        print(f'\n--- Page {p_idx} ---')

        # Text extraction
        text = page.extract_text()
        print(f'Text length: {len(text) if text else 0}')
        if text:
            print(f'First 200 chars:\n{text[:200]}')

        # Contents
        try:
            contents = page.get_contents()
            print(f'Page objects found: {len(contents)}')
            for i, obj in enumerate(contents):
                print(f'  Object[{i}] type: {type(obj).__name__}')
                resolved = obj.get_object() if hasattr(obj, 'get_object') else obj
                data = resolved.get_data()
                print(f'  get_data() returned: {type(data).__name__}, len={len(data) if data else 0}')

                # Try preprocess
                try:
                    decoded = preprocess_page_content(data)
                    print(f'  Decoded length: {len(decoded)}')
                    print(f'  First 300 chars:\n{decoded[:300]}')

                    # Try graphics extraction
                    try:
                        graphics = extract_graphics_string(decoded)
                        print(f'  Graphics blocks: {len(graphics) if graphics else 0}')
                        if graphics:
                            for g_idx, g in enumerate(graphics[:3]):
                                lines = g.split('\n')
                                print(f'    Block[{g_idx}]: {len(lines)} lines, first={lines[0][:80] if lines else "empty"}')
                    except Exception as e:
                        print(f'  extract_graphics_string FAILED: {e}')
                        traceback.print_exc()

                except Exception as e:
                    print(f'  preprocess_page_content FAILED: {e}')
                    traceback.print_exc()

        except Exception as e:
            print(f'get_contents() FAILED: {e}')
            traceback.print_exc()


# Cardiosoft PDFs
for name in os.listdir(os.path.join(BASE, 'data/pdf_data/pdf_cardiosoft/original_ecgs/')):
    if name.endswith('.pdf'):
        inspect_pdf(os.path.join(BASE, 'data/pdf_data/pdf_cardiosoft/original_ecgs/', name), f'Cardiosoft/{name}')

# Schiller PDFs
for name in os.listdir(os.path.join(BASE, 'data/pdf_data/pdf_schiller/original_ecgs/')):
    if name.endswith('.pdf'):
        inspect_pdf(os.path.join(BASE, 'data/pdf_data/pdf_schiller/original_ecgs/', name), f'Schiller/{name}')

print('\nDone.')
