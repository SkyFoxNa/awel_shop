import barcode
from barcode.writer import ImageWriter
from io import BytesIO

def generate_user_barcode(barcode_value: str):
    code_class = barcode.get_barcode_class('code128')
    buffer = BytesIO()
    # options={"write_text": False} — прибирає цифри під штрихкодом
    code_instance = code_class(barcode_value, writer=ImageWriter())
    code_instance.write(buffer, options={"write_text": False, "quiet_zone": 5})
    buffer.seek(0)
    return buffer