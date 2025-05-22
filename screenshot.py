import tempfile
from mss import mss

def take_screenshot() -> str:
    """
    Снимает весь экран и сохраняет во временный файл.
    Возвращает путь к файлу.
    """
    with mss() as sct:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        sct.shot(output=tmp.name)
    return tmp.name
