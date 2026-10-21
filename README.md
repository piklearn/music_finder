# Music Finder

ابزار محلی برای جست‌وجوی آهنگ در **سایت‌هایی که خودت تعریف می‌کنی**، پیدا کردن لینک دانلود و نمایش آن.

- جست‌وجو با **نام آهنگ** یا **بخشی از متن آهنگ** (تشخیص آهنگ از متن با LRCLIB).
- هر سایت یک **پروفایل** است: آدرس جست‌وجو + سلکتورهای CSS. یک بار تعریف می‌کنی، برای همهٔ آهنگ‌ها کار می‌کند.
- **استنباط خودکار سلکتورها** از یک صفحهٔ نمونه.
- مسیر دومرحله‌ای: صفحهٔ نتایج → صفحهٔ آهنگ → لینک دانلود، با چند لایه fallback.
- بررسی لینک با `HEAD`/`Range` (نوع محتوا، حجم، مستقیم بودن) بدون دانلود فایل.
- کش صفحات، احترام به `robots.txt` و محدودیت نرخ درخواست برای هر دامنه.
- رابط وب فارسی و راست‌به‌چپ + تاریخچهٔ جست‌وجو در SQLite.

## مرزها (مهم)

این ابزار **فایل را دانلود نمی‌کند** و از صفحهٔ نتایج، لینک دانلود را پیدا و نمایش می‌دهد؛ باز کردن/ذخیرهٔ فایل با مرورگر خودت انجام می‌شود. همچنین:

- لاگین، کپچا، پرداخت یا DRM را دور نمی‌زند.
- `robots.txt` را نادیده نمی‌گیرد (در صورت نیاز با `respect_robots=False` در `Fetcher` قابل تغییر است، ولی پیش‌فرض محترمانه است).
- مسئولیت رعایت حق نشر و شرایط استفادهٔ هر سایت با کاربر است. برای محتوای دارای مجوز یا سایت خودت استفاده کن.

## نصب و اجرا

### لینوکس / مک

```bash
cd music_finder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

یا فقط:

```bash
./run.sh          # خودش venv را می‌سازد و نصب می‌کند
```

### ویندوز

```bat
cd music_finder
run.bat
```

`run.bat` در اولین اجرا محیط مجازی را می‌سازد و وابستگی‌ها را نصب می‌کند، بعد سرور را بالا می‌آورد.

اگر ترجیح می‌دهی دستی کار کنی (PowerShell):

```powershell
cd music_finder
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

سپس <http://127.0.0.1:8000> را باز کن.

> نکتهٔ ویندوز: اگر `python` کار نکرد، `py -3` را امتحان کن (یا «python» را از Microsoft Store غیرفعال کن). فایل `sites.yaml` همیشه با UTF-8 نوشته می‌شود، پس عنوان‌های فارسی سالم می‌مانند.


## افزودن سایت

### روش ۱: استنباط خودکار (پیشنهادی)

در تب «سایت‌ها»:

1. آدرس یک صفحهٔ **نتایج جست‌وجو** (مثلاً `https://site.com/search?q=hello`) را بده.
2. اگر می‌خواهی، آدرس یک **صفحهٔ آهنگ** نمونه را هم بده.
3. «استنباط سلکتورها» → پیش‌نمایش نتایج و لینک‌های پیدا‌شده را ببین.
4. «اعمال روی فرم» → ذخیره.

### روش ۲: تعریف دستی در `sites.yaml`

```yaml
sites:
  - id: mysite
    name: "سایت من"
    base: "https://site.com"
    search_url: "https://site.com/search?q={query}"
    result_selector: "div.song-row"
    title_selector: "h2 a"
    artist_selector: ".artist"
    detail_link_selector: "h2 a"
    download_selector: "a.dl-btn"
    download_on: detail      # detail | result
    render: http             # js فعلاً فقط برای سازگاری ذخیره می‌شود
    charset: ""              # مثلاً windows-1256 برای سایت‌های قدیمی
    enabled: true
```

نکات:

- `{query}` اجباری است و با کوئری URL-encode شده جایگزین می‌شود.
- اگر لینک دانلود همان صفحهٔ نتایج است، `download_on: result` بگذار.
- اگر سلکتور دانلود پیدا نشد، ابزار خودش لینک‌های دارای `download`/`دانلود`/`.mp3` و تگ‌های `<audio>` را امتحان می‌کند.
- برای سایت‌های جاوااسکریپتی، فعلاً باید API/شبکهٔ آن سایت را پیدا کنی یا سلکتورها را روی خروجی HTML تنظیم کنی؛ حالت `render: js` در نسخهٔ بعدی با Playwright فعال می‌شود.

## نحوهٔ کار

```
query ──(lyrics)──> LRCLIB ──> (artist, title)
      └─> برای هر سایت: search_url(query)
              └─> parse_results(selectors)
                      └─> رتبه‌بندی فازی
                              └─> صفحهٔ آهنگ ──> find_download_links
                                      └─> verify (HEAD/Range) ──> نمایش
```

رتبه‌بندی در `app/normalize.py`: نرمال‌سازی حروف عربی/فارسی، حذف اعراب و نیم‌فاصله، حذف کلمات تزئینی مثل «دانلود/آهنگ/کیفیت»، سپس ترکیب پوشش توکن‌ها و شباهت رشته‌ای.

## API

| متد | مسیر | کار |
| --- | --- | --- |
| GET | `/api/sites` | لیست پروفایل‌ها |
| POST | `/api/sites` | افزودن/ویرایش |
| DELETE | `/api/sites/{id}` | حذف |
| POST | `/api/sites/infer` | استنباط سلکتور از URL نمونه |
| POST | `/api/sites/{id}/test` | اجرای پروفایل روی یک کوئری |
| POST | `/api/search` | جست‌وجوی اصلی |
| GET/DELETE | `/api/history` | تاریخچه |
| POST | `/api/cache/clear` | پاک کردن کش |

نمونه:

```bash
curl -s http://127.0.0.1:8000/api/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"hello adele","mode":"title","site_ids":["mysite"]}'
```

## تست

```bash
pip install -r requirements-dev.txt
pytest -q
```

## ساختار

```
app/
  main.py       API و سرو کردن UI
  resolve.py    جست‌وجو → صفحهٔ آهنگ → لینک دانلود + fallback
  infer.py      حدس سلکتورها از صفحهٔ نمونه
  normalize.py  نرمال‌سازی فارسی و رتبه‌بندی
  fetcher.py    HTTP محترمانه: throttle، robots، کش
  verify.py     اعتبارسنجی لینک بدون دانلود
  lyrics.py     تشخیص آهنگ از متن (LRCLIB)
  profiles.py   ذخیره/خواندن sites.yaml
  cache.py      کش SQLite صفحات
  history.py    تاریخچهٔ جست‌وجو
static/         UI (vanilla JS + CSS)
templates/      index.html
data/           cache.sqlite و history.sqlite (خودکار ساخته می‌شوند)
```

## عیب‌یابی

- **نتیجه صفر:** با «تست» همان سایت را بررسی کن؛ اغلب `result_selector` یا `detail_link_selector` اشتباه است یا نتایج با JS ساخته می‌شوند.
- **لینک دانلود پیدا نشد:** سلکتور را دقیق‌تر کن یا صفحهٔ آهنگ نمونه را در استنباط بده.
- **متن فارسی خراب است:** `charset` را روی `windows-1256` بگذار.
- **خطای ۴۰۳:** سایت در `robots.txt` اجازه نداده است.
