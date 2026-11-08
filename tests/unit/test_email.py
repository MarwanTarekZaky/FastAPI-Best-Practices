from app.worker.tasks import _qr_code_image


def test_qr_code_is_an_inline_png():
    attachment = _qr_code_image("123456", "delivery_code")

    # The template shows it with <img src="cid:delivery_code">
    assert attachment["headers"]["Content-ID"] == "<delivery_code>"
    assert attachment["headers"]["Content-Disposition"].startswith("inline")
    assert attachment["file"].file.read().startswith(b"\x89PNG")
