import threading
import keyboard
from mss import mss
from tempfile import NamedTemporaryFile
from pathlib import Path

from telegram_sender import send_photo, send_message
from ai_solver import solve_image

def take_screenshot() -> str:
    with mss() as sct:
        tmp = NamedTemporaryFile(suffix=".png", delete=False)
        sct.shot(output=tmp.name)
    return tmp.name

def handler(prompt: str):
    tmp_path = None
    try:
        # 1) делаем скрин и сразу шлём фото
        tmp_path = take_screenshot()
        send_photo(tmp_path, caption=prompt)

        # 2) распознаём текст здесь, чтобы вывести
        from PIL import Image
        import pytesseract

        img = Image.open(Path(tmp_path))
        ocr_text = pytesseract.image_to_string(
            img, lang="rus+eng", config="--oem 3 --psm 6"
        ).strip()

        # 3) Печатаем полный текст, который пойдёт на вход AI
        full_text = f"{prompt}\n\n{ocr_text}"
        print("\n=== Full text sent to AI ===")
        print(full_text)
        print("=== End of full text ===\n")

        # 4) А теперь вызываем AI и отправляем его ответ
        answer = solve_image(tmp_path, prompt)
        send_message(answer)

    except Exception as e:
        print("Error in handler:", e)
    finally:
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink()

def main():
    print("Screenshot-to-Telegram bot")
    print("Press Alt+number to capture and send.")

    # Hotkey 1: Alt+Q → prompt #1
    keyboard.add_hotkey(
        "alt+1",
        lambda: threading.Thread(
            target=handler,
            args=("""
            Я получил задачу на мок-интервью по бэкенду питона в Яндекс. Помоги мне понять, к какому типу она относится:Что именно нужно сделать? Какие данные я получаю на вход?
            Что конкретно нужно вернуть на выходе?Какие есть ограничения (например, время, объем данных)? Объясни максимально просто, понятно, как для школьника., 
            только без сложных конструкций. попроще
            """
                  ,),
            daemon=True
        ).start()
    )

    # Hotkey 2: Alt+W → prompt #2
    keyboard.add_hotkey(
        "alt+2",
        lambda: threading.Thread(
            target=handler,
            args=("""
            Я получил задачу на мок-интервью по бэкенду питона в Яндекс. Какой алгоритм используется для решения данной задачи. Он типовой?
            Напиши типовое решение этого алгоритма и его название
            Используй понятный и простой язык, без сложных терминов., только без сложных конструкций. попроще
            """,),
            daemon=True
        ).start()
    )

    keyboard.add_hotkey(
        "alt+3",
        lambda: threading.Thread(
            target=handler,
            args=("""
            Я получил задачу на мок-интервью по бэкенду питона в Яндекс. Мне нужно придумать простой алгоритм для решения задачи. Опиши мне шаг за шагом, как решать такую задачу. 
            Используй простые фразы и разбей алгоритм на понятные этапы. Обязательно поясни каждое действие и почему именно так нужно сделать. 
            Сделай так, чтобы любой школьник легко понял этот алгоритм., только без сложных конструкций. попроще
            """,),
            daemon=True
        ).start()
    )

    keyboard.add_hotkey(
        "alt+4",
        lambda: threading.Thread(
            target=handler,
            args=("""
             Я получил задачу на мок-интервью по бэкенду питона в Яндекс. Для решения моей задачи нужно выбрать подходящую структуру данных в Python. 
             Назови, какая структура данных лучше всего подходит и почему (список, словарь, множество, очередь или другая).  
             Объясни простыми словами, зачем использовать именно эту структуру. Приведи небольшой понятный пример, как это будет выглядеть в коде., только без сложных конструкций. попроще
            """,),
            daemon=True
        ).start()
    )

    keyboard.add_hotkey(
        "alt+5",
        lambda: threading.Thread(
            target=handler,
            args=("""
            Я получил задачу на мок-интервью по бэкенду питона в Яндекс. Теперь нужно написать код для решения задачи.  
            Помоги разбить написание кода на маленькие и простые шаги. Каждый шаг опиши максимально понятно, объясняя, что именно я должен сделать. 
            Не пиши сразу весь код целиком, а покажи пример реализации по кусочкам. Используй простой и понятный язык, чтобы я легко понял каждую часть кода. 
            В конце напиши полный код решения задачи, только без сложных конструкций. попроще
            """,),
            daemon=True
        ).start()
    )

    keyboard.add_hotkey(
        "alt+6",
        lambda: threading.Thread(
            target=handler,
            args=("""
                Я получил задачу на мок-интервью по бэкенду питона в Яндекс. Я хочу заранее подготовиться к возможным вопросам на интервью.  
                Ответь простым языком на следующие вопросы о моем решении: Какие и Почему именно такие структуры данных мы использовали в решении?  
                Какая будет сложность моего алгоритма и что это значит простыми словами?  Как можно было бы улучшить мой код, если бы было больше времени?  
                Объясняй максимально понятно, чтобы я мог легко пересказать это своими словами. , только без сложных конструкций. попроще
                """,),
            daemon=True
        ).start()
    )

    keyboard.add_hotkey(
        "alt+7",
        lambda: threading.Thread(
            target=handler,
            args=("""
                    Я получил задачу на мок-интервью по бэкенду питона в Яндекс. Мне нужно краткое описание решения по пунктам, напиши текстом. 
                    Как бы ты его рассказал, напиши это текстом., только без сложных конструкций. попроще
                    """,),
            daemon=True
        ).start()
    )

    keyboard.add_hotkey(
        "alt+8",
        lambda: threading.Thread(
            target=handler,
            args=("""
                        Я получил задачу на мок-интервью по бэкенду питона в Яндекс. напиши только полное решение и комментарии к нему, только без сложных конструкций. попроще.
                        """,),
            daemon=True
        ).start()
    )

    keyboard.add_hotkey(
        "alt+9",
        lambda: threading.Thread(
            target=handler,
            args=("""
                            Я получил задачу на мок-интервью по бэкенду питона в Яндекс. напиши только полное решение без комментариев, только без сложных конструкций. попроще.
                            """,),
            daemon=True
        ).start()
    )

    keyboard.wait()

if __name__ == "__main__":
    main()
