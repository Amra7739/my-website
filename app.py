from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
import sqlite3
import os
import contextlib
from pathlib import Path
import csv
import io
import uuid
import shutil
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "ih-zasag-college-secret-key"

DATABASE = Path(__file__).resolve().parent / "college.db"
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


class UnifiedCursor:
    def __init__(self, raw_cur, is_pg=False):
        self._cur = raw_cur
        self._is_pg = is_pg

    def execute(self, sql, params=None):
        if self._is_pg:
            adapted_sql = self._adapt_sql(sql)
            if params is not None:
                return self._cur.execute(adapted_sql, params)
            return self._cur.execute(adapted_sql)
        else:
            if params is not None:
                return self._cur.execute(sql, params)
            return self._cur.execute(sql)

    def executemany(self, sql, seq_of_params):
        if self._is_pg:
            adapted_sql = self._adapt_sql(sql)
            return self._cur.executemany(adapted_sql, seq_of_params)
        return self._cur.executemany(sql, seq_of_params)

    def _adapt_sql(self, sql):
        s = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        s = s.replace("INTEGER PRIMARY KEY", "SERIAL PRIMARY KEY")
        if "ADD COLUMN " in s and "ADD COLUMN IF NOT EXISTS " not in s:
            s = s.replace("ADD COLUMN ", "ADD COLUMN IF NOT EXISTS ")
        if "INSERT OR IGNORE INTO site_settings" in s:
            s = s.replace("INSERT OR IGNORE INTO site_settings", "INSERT INTO site_settings")
            if "ON CONFLICT" not in s:
                s += " ON CONFLICT (key) DO NOTHING"
        s = s.replace("?", "%s")
        return s

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def lastrowid(self):
        return getattr(self._cur, "lastrowid", None)


class UnifiedConnection:
    def __init__(self, raw_conn, is_pg=False):
        self._conn = raw_conn
        self._is_pg = is_pg

    def cursor(self):
        if self._is_pg:
            import psycopg2.extras
            return UnifiedCursor(self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor), is_pg=True)
        return UnifiedCursor(self._conn.cursor(), is_pg=False)

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    @property
    def row_factory(self):
        return getattr(self._conn, "row_factory", None)

    @row_factory.setter
    def row_factory(self, val):
        if not self._is_pg:
            self._conn.row_factory = val


@contextlib.contextmanager
def get_db():
    if DATABASE_URL:
        import psycopg2
        raw_conn = psycopg2.connect(DATABASE_URL)
        conn = UnifiedConnection(raw_conn, is_pg=True)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        with sqlite3.connect(DATABASE) as raw_conn:
            raw_conn.row_factory = sqlite3.Row
            conn = UnifiedConnection(raw_conn, is_pg=False)
            yield conn


@app.before_request
def sync_static_assets():
    try:
        src_static = Path(r"C:\Users\Dell\Documents\flask.lab\static")
        dst_static = Path(__file__).resolve().parent / "static"
        dst_static.mkdir(parents=True, exist_ok=True)
        if src_static.exists() and src_static.resolve() != dst_static.resolve():
            for img_name in [
                "bolortuya.png", "bolortuya_full.png", "davaadorj.png",
                "news_horog.png", "news_tsever_bichig.png", "news_altan_honh.png", "news_sagsan_bumbug.png",
                "teacher_dorjkhand.png", "teacher_gantsetseg.png", "teacher_oyungerel.png",
                "teacher_temuulen.png", "teacher_enkhtuya.png", "teacher_sarangerel.png",
                "teacher_munkherdene.png", "teacher_oyunerdene.png", "teacher_nyamsuren.png",
                "logo.png", "logo.jpg", "logo_full.png", "logo_transparent.png", "logo_emblem_transparent.png"
            ]:
                s, d = src_static / img_name, dst_static / img_name
                if s.exists():
                    if not d.exists() or s.stat().st_mtime > d.stat().st_mtime:
                        shutil.copy2(s, d)
    except Exception:
        pass
UPLOAD_FOLDER = Path(__file__).resolve().parent / "static" / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_image(file_key, prefix="img"):
    if file_key in request.files:
        file = request.files[file_key]
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{prefix}_{uuid.uuid4().hex[:10]}.{ext}"
            filepath = UPLOAD_FOLDER / filename
            file.save(filepath)
            return f"/static/uploads/{filename}"
    return None


DEFAULT_SETTINGS = {
    "academic_year": "2026–2027",
    "admission_status": "Элсэлтийн цахим бүртгэл нээлттэй явагдаж байна",
    "phone_1": "7711-9696",
    "phone_2": "7015-7765",
    "email": "info@ikhzasag.edu.mn",
    "address": "Улаанбаатар хот, Баянзүрх дүүрэг, 30-р хороо, Доржийн гудамж, Их Засаг цогцолбор",
    "work_hours": "Даваа–Баасан 08:30–17:30, Бямба 10:00–15:00",
    "stat_majors": "17+",
    "stat_students": "1,250+",
    "stat_teachers": "45+",
    "stat_employment": "95%",
    "stipend_amount": "200,000₮",
    "director_name": "Л. Болортуяа",
    "director_title": "Боловсрол судлалын магистр · Тэргүүлэх багш · Боловсролын тэргүүний ажилтан",
    "director_quote": "Их Засаг Политехник Коллеж нь оюутан залуусдаа зөвхөн онолын мэдлэг олгоод зогсохгүй бодит амьдрал, үйлдвэрлэл дээр шууд ажиллах дадлага чадварыг эзэмшүүлэхийг гол зорилгоо болгон ажилладаг. Бидний төгсөгчид хөдөлмөрийн зах зээлд өндөр үнэлэгдэж, салбар бүртээ амжилттай манлайлж байгаад бид ямагт бахархдаг.",
    "facebook_url": "https://www.facebook.com/ikhzasag",
    "website_url": "https://www.ikhzasag.edu.mn"
}


def init_db():
    try:
        src_static = Path(r"C:\Users\Dell\Documents\flask.lab\static")
        dst_static = Path(__file__).resolve().parent / "static"
        dst_static.mkdir(parents=True, exist_ok=True)
        if src_static.exists() and src_static.resolve() != dst_static.resolve():
            for img_name in [
                "news_horog.png", "news_tsever_bichig.png", "news_altan_honh.png", "news_sagsan_bumbug.png",
                "davaadorj.png", "bolortuya.png", "bolortuya_full.png",
                "teacher_dorjkhand.png", "teacher_gantsetseg.png", "teacher_oyungerel.png",
                "teacher_temuulen.png", "teacher_enkhtuya.png", "teacher_sarangerel.png",
                "teacher_munkherdene.png", "teacher_oyunerdene.png", "teacher_nyamsuren.png",
                "logo.png", "logo.jpg", "logo_full.png", "logo_transparent.png", "logo_emblem_transparent.png"
            ]:
                s, d = src_static / img_name, dst_static / img_name
                if s.exists():
                    shutil.copy2(s, d)
    except Exception:
        pass

    with get_db() as conn:
        # 1. Элсэлтийн бүртгэлийн хүснэгт
        conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullname TEXT NOT NULL,
                birthdate TEXT NOT NULL,
                gender TEXT NOT NULL,
                major TEXT NOT NULL,
                phone TEXT NOT NULL,
                status TEXT DEFAULT 'Шинэ',
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for col_sql in [
            "ALTER TABLE applications ADD COLUMN status TEXT DEFAULT 'Шинэ'",
            "ALTER TABLE applications ADD COLUMN notes TEXT DEFAULT ''"
        ]:
            try:
                conn.execute(col_sql)
            except Exception:
                pass

        # 2. Мэдээ, зарлалын хүснэгт
        conn.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                summary TEXT NOT NULL,
                content TEXT,
                image TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            conn.execute("ALTER TABLE news ADD COLUMN image TEXT")
        except Exception:
            pass

        # 3. Багш, удирдлагын хүснэгт
        conn.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                degree TEXT DEFAULT '',
                department TEXT DEFAULT 'Мэргэжлийн тэнхим',
                experience_years TEXT DEFAULT '10+ жил',
                bio TEXT DEFAULT '',
                email TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                photo TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 4. Мэргэжил, хөтөлбөрүүдийн хүснэгт
        conn.execute("""
            CREATE TABLE IF NOT EXISTS majors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                category_label TEXT NOT NULL,
                duration TEXT NOT NULL,
                base_edu TEXT NOT NULL,
                stipend TEXT NOT NULL,
                diploma TEXT NOT NULL,
                pathway TEXT NOT NULL,
                description TEXT NOT NULL,
                career TEXT DEFAULT '',
                featured INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 5. Түгээмэл асуулт хариултын хүснэгт (FAQ)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS faqs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 6. Сайтын тохиргооны хүснэгт
        conn.execute("""
            CREATE TABLE IF NOT EXISTS site_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        cur = conn.cursor()

        # Тохиргооны анхны утгуудыг оруулах
        for k, v in DEFAULT_SETTINGS.items():
            cur.execute("INSERT OR IGNORE INTO site_settings (key, value) VALUES (?, ?)", (k, v))

        # Сургуулийн захирлын нэр болон цолыг Л. Болортуяа болгож шинэчлэх
        cur.execute("UPDATE site_settings SET value = 'Л. Болортуяа' WHERE key = 'director_name' AND value = 'Д. Даваадорж'")
        cur.execute("UPDATE site_settings SET value = 'Боловсрол судлалын магистр · Тэргүүлэх багш · Боловсролын тэргүүний ажилтан' WHERE key = 'director_title' AND value LIKE '%Дэд профессор%'")

        # Мэдээний анхны бодит өгөгдөл
        cur.execute("SELECT COUNT(*) FROM news")
        news_count = cur.fetchone()[0]
        if news_count == 0:
            sample_news = [
                (
                    "2026-2027 оны хичээлийн жилийн элсэлтийн цахим бүртгэл албан ёсоор эхэллээ",
                    "Элсэлт",
                    "Их Засаг Политехник Коллеж нь 2026-2027 оны хичээлийн жилд 9 болон 12-р анги төгсөгчдийг 17 чиглэлийн эрэлттэй мэргэжлээр элсүүлж байна. 9-р анги суурьтай суралцагч бүр сар бүр 200,000₮-ийн тэтгэлэгт хамрагдана.",
                    "Эрхэм хүндэт элсэгчид, эцэг эхчүүдийн анхааралд:\n\nИх Засаг Политехник Коллеж нь хөдөлмөрийн зах зээлийн эрэлтэд нийцсэн чадамжид суурилсан мэргэжлийн боловсрол олгох 2026-2027 оны хичээлийн жилийн элсэлтийн албан ёсны бүртгэлээ эхлүүллээ.\n\nКоллежид суралцах гол давуу талууд:\n- Төрөөс сар бүр олгох 200,000₮-ийн буцалтгүй тэтгэлэг\n- Орчин үеийн тоног төхөөрөмж бүхий мэргэжлийн дадлагын лабораториуд\n- Төгсөгчдийн 95% ажлын байрны шууд зуучлал болон цалинтай дадлага\n- Их Засаг ОУИС-ийн бакалаврын хөтөлбөрийн 2-р дамжаанд шууд шатлан суралцах эрх\n\nБүрдүүлэх материал:\n1. Суурь боловсролын гэрчилгээ (9-р анги) эсвэл Бүрэн дунд боловсролын үнэмлэх (12-р анги)\n2. Иргэний үнэмлэхийн лавлагаа (E-Mongolia)\n3. Цээж зураг 3x4 хэмжээтэй 4 хувь\n\nЦахимаар бүртгүүлэхийг хүсвэл манай вэбсайтын 'Элсэх' цэсээр орж анкет илгээнэ үү.",
                    "https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=800&q=80"
                ),
                (
                    "БНСУ-ын Кён-Ин коллежтой хамтарсан 1+1 олон улсын хөтөлбөрийн элсэлт зарлагдлаа",
                    "Олон улс",
                    "Монголд 1 жил, БНСУ-д 1 жил суралцан хоёр улсын хос диплом эзэмших, Солонгос улсад цалинтай дадлага хийх олон улсын аялал жуулчлалын хөтөлбөрийн сонгон шалгаруулалт явагдаж байна.",
                    "Чингис Хааны нэрэмжит Их Засаг Олон Улсын Их Сургуулийн харьяа Их Засаг Политехник Коллеж болон БНСУ-ын Инчон хотын Кён-Ин Эмэгтэйчүүдийн Их Сургуулийн коллеж хоорондын хамтын ажиллагааны гэрээний хүрээнд Аялал жуулчлал, Зочид буудлын 1+1 хөтөлбөрийн шинэ элсэлт зарлагдлаа.\n\nХөтөлбөрийн онцлог:\n- Эхний 1 жил Монголдоо Их Засаг Политехник Коллежид мэргэжлийн суурь болон Солонгос хэлний эрчимжүүлсэн сургалтад суралцана.\n- Дараагийн 1 жил БНСУ-ын Кён-Ин коллежид суралцаж, Солонгосын аялал жуулчлал, зочид буудлын салбарт цалинтай дадлага хийнэ.\n- Төгсөхдөө Монгол Улс болон БНСУ-ын албан ёсны хос диплом гардан авна.\n\nДэлгэрэнгүй мэдээллийг 7711-9696, 7015-7765 утсаар авна уу.",
                    "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?auto=format&fit=crop&w=800&q=80"
                ),
                (
                    "Шилдэг суралцагчдад зориулсан 'Их Засаг сан'-гийн нэрэмжит тэтгэлэг зарлагдлаа",
                    "Тэтгэлэг",
                    "Сурлага, урлаг, спортын онцгой амжилт гаргасан суралцагчдад сургалтын төлбөрийн 20-50%-ийн хөнгөлөлт үзүүлэх Их Засаг сангийн нэрэмжит тэтгэлэгт хөтөлбөр хэрэгжиж эхэллээ.",
                    "Их Засаг Политехник Коллеж нь авьяаслаг, хичээл зүтгэлтэй суралцагчдаа урамшуулах, нийгмийн хариуцлагын хүрээнд дэмжлэг үзүүлэх зорилгоор жил бүр 'Их Засаг сан'-гийн нэрэмжит тэтгэлгийг олгодог.\n\nТэтгэлгийн төрлүүд:\n1. Сурлагын онцгой амжилтын тэтгэлэг (Төлбөрийн 50% хүртэл)\n2. Улс, хот, дүүргийн олимпиад, урлаг спортын уралдааны медальт элсэгч (Төлбөрийн 20-40%)\n3. Нэг гэр бүлээс 2 ба түүнээс дээш суралцагч суралцвал (Төлбөрийн 10-20%)\n4. 'Супер студент' олон улсын солилцооны тэтгэлэг\n\nТэтгэлэгт хамрагдах хүсэлт болон холбогдох баримт бичгийг коллежийн Сургалтын албаны 204 тоотод хүлээн авч байна.",
                    "https://images.unsplash.com/photo-1541339907198-e08756dedf3f?auto=format&fit=crop&w=800&q=80"
                ),
                (
                    "График дизайн болон Вэб хөгжүүлэлтийн шинэчлэгдсэн мультимедиа лаборатори ашиглалтад орлоо",
                    "Оюутны амьдрал",
                    "Сүүлийн үеийн өндөр хүчин чадалтай график станц компьютерууд, дижитал зургийн планшет болон хэвлэлийн тоног төхөөрөмжөөр бүрэн тоноглогдсон шинэ лаборатори нээлтээ хийлээ.",
                    "Их Засаг Политехник Коллежийн 'Хэвлэлийн график дизайнер' болон 'Вэб дизайн' мэргэжлийн ангийн суралцагчдад зориулсан орчин үеийн мультимедиа, график дизайны лаборатори бүрэн шинэчлэгдэж ашиглалтад орлоо.\n\nТус лаборатори нь:\n- Өндөр үзүүлэлттэй 30 гаруй график компьютер\n- Мэргэжлийн Wacom дижитал зургийн планшетууд\n- Өнгө ялгалт болон хэвлэлийн эх бэлтгэлийн тоног төхөөрөмж\n- Өндөр хурдны шилэн кабелийн интернэт орчноор бүрэн хангагдсан.\n\nИнгэснээр суралцагчид сургууль дээрээ бодит захиалгат ажлууд, брендинг, вэб аппликейшны төслүүд дээр багшаар удирдуулан ажиллах бүрэн боломжтой болж байна.",
                    "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?auto=format&fit=crop&w=800&q=80"
                ),
                (
                    "Мэргэжлийн боловсролын сургуулиудын 'Ур чадвар-2026' уралдаанд манай оюутнууд тэргүүллээ",
                    "Оюутны амьдрал",
                    "Хоол үйлдвэрлэл, Хувцас дизайн, График дизайны төрлүүдэд Их Засаг Политехник Коллежийн баг тамирчид 2 алт, 1 мөнгөн медаль хүртэж өндөр амжилт үзүүллээ.",
                    "Монгол Улсын хэмжээнд үйл ажиллагаа явуулж буй политехник коллеж, МСҮТ-үүдийн дунд жил бүр зохион байгуулагддаг 'Мэргэжлийн ур чадвар' улсын уралдаанд Их Засаг Политехник Коллежийн суралцагчид амжилттай оролцлоо.\n\nГаргасан амжилтууд:\n- Хоолны үйлчилгээ (Тогооч) төрөлд 3-р дамжааны суралцагч Э.Төгөлдөр Тэргүүн байр\n- Хувцасны загвар зохион бүтээгч төрөлд 3-р дамжааны суралцагч Б.Номин Тэргүүн байр\n- Хэвлэлийн график дизайн төрөлд 2-р дамжааны суралцагч Г.Тэмүүжин Дэд байр тус тус эзэллээ.\n\nАмжилт гаргасан нийт суралцагчид болон удирдсан мэргэжлийн багш нартаа баяр хүргэе!",
                    "https://images.unsplash.com/photo-1556761175-5973dc0f32e7?auto=format&fit=crop&w=800&q=80"
                ),
                (
                    "Түнш 50 гаруй аж ахуйн нэгж оролцсон 'Ажлын байрны нээлттэй өдөрлөг' боллоо",
                    "Зарлал",
                    "Төгсөх дамжааны суралцагчдыг ажлын байранд шууд зуучлах, цалинтай үйлдвэрлэлийн дадлагад хамруулах зорилготой хөдөлмөрийн яармаг амжилттай зохион байгуулагдлаа.",
                    "Их Засаг Политехник Коллеж нь төгсөгчдийнхөө хөдөлмөр эрхлэлтийг дэмжих зорилгоор жил бүр уламжлал болгон зохион байгуулдаг 'Ажлын байрны нээлттэй өдөрлөг'-ийг Их Засаг цогцолборт амжилттай зохион байгууллаа.\n\nӨдөрлөгт Улаанбаатар хотын тэргүүлэх хэвлэлийн компаниуд, Шангри-Ла болон Кемпински зэрэг олон улсын сүлжээ зочид буудлууд, загварын урлангууд, эмнэлэг, барилга угсралтын нийт 54 аж ахуйн нэгж оролцож, төгсөх ангийн 280 гаруй оюутанд ажлын байрны урилга болон цалинтай дадлагын гэрээ гардууллаа.",
                    "https://images.unsplash.com/photo-1521737711867-e3b97375f902?auto=format&fit=crop&w=800&q=80"
                )
            ]
            cur.executemany("""
                INSERT INTO news (title, category, summary, content, image)
                VALUES (?, ?, ?, ?, ?)
            """, sample_news)
        else:
            cur.execute("UPDATE news SET image = 'https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=800&q=80' WHERE id = 1 AND (image IS NULL OR image = '')")
            cur.execute("UPDATE news SET image = 'https://images.unsplash.com/photo-1523050854058-8df90110c9f1?auto=format&fit=crop&w=800&q=80' WHERE id = 2 AND (image IS NULL OR image = '')")
            cur.execute("UPDATE news SET image = 'https://images.unsplash.com/photo-1541339907198-e08756dedf3f?auto=format&fit=crop&w=800&q=80' WHERE id = 3 AND (image IS NULL OR image = '')")
            if news_count <= 3:
                extra_news = [
                    (
                        "График дизайн болон Вэб хөгжүүлэлтийн шинэчлэгдсэн мультимедиа лаборатори ашиглалтад орлоо",
                        "Оюутны амьдрал",
                        "Сүүлийн үеийн өндөр хүчин чадалтай график станц компьютерууд, дижитал зургийн планшет болон хэвлэлийн тоног төхөөрөмжөөр бүрэн тоноглогдсон шинэ лаборатори нээлтээ хийлээ.",
                        "Их Засаг Политехник Коллежийн 'Хэвлэлийн график дизайнер' болон 'Вэб дизайн' мэргэжлийн ангийн суралцагчдад зориулсан орчин үеийн мультимедиа, график дизайны лаборатори бүрэн шинэчлэгдэж ашиглалтад орлоо.\n\nТус лаборатори нь:\n- Өндөр үзүүлэлттэй 30 гаруй график компьютер\n- Мэргэжлийн Wacom дижитал зургийн планшетууд\n- Өнгө ялгалт болон хэвлэлийн эх бэлтгэлийн тоног төхөөрөмж\n- Өндөр хурдны шилэн кабелийн интернэт орчноор бүрэн хангагдсан.\n\nИнгэснээр суралцагчид сургууль дээрээ бодит захиалгат ажлууд, брендинг, вэб аппликейшны төслүүд дээр багшаар удирдуулан ажиллах бүрэн боломжтой болж байна.",
                        "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?auto=format&fit=crop&w=800&q=80"
                    ),
                    (
                        "Мэргэжлийн боловсролын сургуулиудын 'Ур чадвар-2026' уралдаанд манай оюутнууд тэргүүллээ",
                        "Оюутны амьдрал",
                        "Хоол үйлдвэрлэл, Хувцас дизайн, График дизайны төрлүүдэд Их Засаг Политехник Коллежийн баг тамирчид 2 алт, 1 мөнгөн медаль хүртэж өндөр амжилт үзүүллээ.",
                        "Монгол Улсын хэмжээнд үйл ажиллагаа явуулж буй политехник коллеж, МСҮТ-үүдийн дунд жил бүр зохион байгуулагддаг 'Мэргэжлийн ур чадвар' улсын уралдаанд Их Засаг Политехник Коллежийн суралцагчид амжилттай оролцлоо.\n\nГаргасан амжилтууд:\n- Хоолны үйлчилгээ (Тогооч) төрөлд 3-р дамжааны суралцагч Э.Төгөлдөр Тэргүүн байр\n- Хувцасны загвар зохион бүтээгч төрөлд 3-р дамжааны суралцагч Б.Номин Тэргүүн байр\n- Хэвлэлийн график дизайн төрөлд 2-р дамжааны суралцагч Г.Тэмүүжин Дэд байр тус тус эзэллээ.\n\nАмжилт гаргасан нийт суралцагчид болон удирдсан мэргэжлийн багш нартаа баяр хүргэе!",
                        "https://images.unsplash.com/photo-1556761175-5973dc0f32e7?auto=format&fit=crop&w=800&q=80"
                    ),
                    (
                        "Түнш 50 гаруй аж ахуйн нэгж оролцсон 'Ажлын байрны нээлттэй өдөрлөг' боллоо",
                        "Зарлал",
                        "Төгсөх дамжааны суралцагчдыг ажлын байранд шууд зуучлах, цалинтай үйлдвэрлэлийн дадлагад хамруулах зорилготой хөдөлмөрийн яармаг амжилттай зохион байгуулагдлаа.",
                        "Их Засаг Политехник Коллеж нь төгсөгчдийнхөө хөдөлмөр эрхлэлтийг дэмжих зорилгоор жил бүр уламжлал болгон зохион байгуулдаг 'Ажлын байрны нээлттэй өдөрлөг'-ийг Их Засаг цогцолборт амжилттай зохион байгууллаа.\n\nӨдөрлөгт Улаанбаатар хотын тэргүүлэх хэвлэлийн компаниуд, Шангри-Ла болон Кемпински зэрэг олон улсын сүлжээ зочид буудлууд, загварын урлангууд, эмнэлэг, барилга угсралтын нийт 54 аж ахуйн нэгж оролцож, төгсөх ангийн 280 гаруй оюутанд ажлын байрны урилга болон цалинтай дадлагын гэрээ гардууллаа.",
                        "https://images.unsplash.com/photo-1521737711867-e3b97375f902?auto=format&fit=crop&w=800&q=80"
                    )
                ]
                cur.executemany("""
                    INSERT INTO news (title, category, summary, content, image)
                    VALUES (?, ?, ?, ?, ?)
                """, extra_news)

        # Тестээр үүссэн түр мэдээнүүдийг цэвэрлэх
        cur.execute("DELETE FROM news WHERE title IN ('zarlal', 'Shine aduunii mah zarna')")

        # Албан ёсны ikhzasag.edu.mn/schools/ikh-zasag-politekhnik-kollezh дээрх 4 сургуулийн мэдээллийг нэмэх
        cur.execute("SELECT COUNT(*) FROM news WHERE image = '/static/news_horog.png'")
        if cur.fetchone()[0] == 0:
            official_school_news = [
                (
                    "САГСАН БӨМБӨГИЙН БАГИЙН ШИЛДГҮҮД ТОДОРЛОО",
                    "Оюутны амьдрал",
                    "Их Засаг Политехник Коллежийн аварга шалгаруулах сагсан бөмбөгийн тэмцээн эрэгтэй, эмэгтэй багуудын дунд амжилттай зохион байгуулагдаж шилдгүүдээ тодрууллаа.",
                    "Их Засаг Политехник Коллежийн суралцагчдын чөлөөт цагийг зөв боловсон өнгөрүүлэх, бие бялдрыг чийрэгжүүлэх, багийн спортыг хөгжүүлэх зорилгоор зохион байгуулагдсан сургуулийн аварга шалгаруулах сагсан бөмбөгийн тэмцээн амжилттай өндөрлөлөө.\n\nЭрэгтэй багийн дүнгээр:\n- Алтан медаль: Жэсан 2+2 хөтөлбөрийн I курсийн баг\n- Мөнгөн медаль: Хэвлэлийн график дизайны 203-р бүлгийн баг\n- Хүрэл медаль: Хэвлэлийн график дизайны 302-р бүлгийн баг\n\nЭмэгтэй багийн дүнгээр:\n- Алтан медаль: Жэсан 2+2 хөтөлбөрийн I курсийн баг\n- Мөнгөн медаль: Зочид буудал, зоогийн газрын үйлчилгээний ажилтны 206-р бүлгийн баг\n- Хүрэл медаль: Үсчин гоо сайхны 304-р бүлгийн баг тус тус шалгарлаа.",
                    "/static/news_sagsan_bumbug.png",
                    "2020-10-23"
                ),
                (
                    "“ АЛТАН ХОНХ”",
                    "Оюутны амьдрал",
                    "Оюутан суралцагчдын танин мэдэхүйн мэдлэгийн цар хүрээг тэлэх, ой тогтоолт, сэтгэн бодох чадварыг хөгжүүлэх 'Алтан хонх' танин мэдэхүйн тэмцээн боллоо.",
                    "Суралцагчдын танин мэдэхүйн мэдлэгийн цар хүрээг нэмэгдүүлж, үзэл бодлоо чөлөөтэй илэрхийлэх, сонсгол, хараа зүй, ой тогтоолтын чадавхыг хөгжүүлэх зорилготой 'Алтан хонх' тэмцээн амжилттай зохион байгуулагдлаа.\n\nТэмцээнд Хэвлэлийн график дизайн болон бусад мэргэжлийн ангийн суралцагчид авхаалж самбаа, мэдлэг оюунаараа өрсөлдөж, ХГД 102-р бүлгийн суралцагч Х.Анхбаяр, Б.Хишигтогтох, Э.Жаргалмаа нар бусдыгаа хошуучлан 'Алтан хонх'-ын эздээр тодорлоо.",
                    "/static/news_altan_honh.png",
                    "2020-10-26"
                ),
                (
                    "“ЦЭВЭР БИЧИГТЭН” ШАЛГАРУУЛЛАА.",
                    "Оюутны амьдрал",
                    "Суралцагчдад зөв сайхан бичих чадвар эзэмшүүлэх, бичгийн соёл, найруулга зүй, эх хэлний дархлааг сайжруулах зорилготой 'Цэвэр бичигтэн' уралдааны дүн гарлаа.",
                    "Их Засаг Политехник Коллежоос суралцагчдад зөв сайхан бичих чадвар эзэмшүүлэх, бичгийн соёл, найруулга зүй, эх хэлний дархлааг сайжруулах, цогц боловсрол олгож өв тэгш хүмүүжүүлэх зорилгоор жил бүр уламжлал болгон зохион байгуулдаг 'Цэвэр бичигтэн' уралдаан амжилттай болж өндөрлөлөө.\n\nУралдаанд I-III дамжааны суралцагчид хичээнгүй бичгийн тиг, монгол бичгийн уран бичлэгээр оролцож, шилдэг бүтээлүүдийг шалгаруулан өргөмжлөл, дурсгалын зүйлээр шагнаж урамшууллаа.",
                    "/static/news_tsever_bichig.png",
                    "2020-10-26"
                ),
                (
                    "“ХӨРӨГ ” ҮЗЭСГЭЛЭН",
                    "Оюутны амьдрал",
                    "Хэвлэлийн график дизайн мэргэжлийн суралцагчдын дунд зохион байгуулагдсан харандаан хөрөг зургийн уралдаан болон 44 бүтээлийн үзэсгэлэн дэлгэгдлээ.",
                    "Их Засаг Политехник Коллежийн Хэвлэлийн график дизайн (ХГД) мэргэжлийн I–III курсийн суралцагчдын дунд 'Хөрөг зураг хэн сайн зурах вэ?' сэдэвт уралдаан амжилттай болж өнгөрлөө.\n\nУралдаанд ХГД-ийн I–II курсийн 44 суралцагч бичгийн цаасан дээр өнгө холихгүйгээр зөвхөн харандаан бүтээлээр өрсөлдөж, шалгарсан 44 бүтээлээр 14 хоногийн турш (10.12–10.22) сургуулийн үзэсгэлэнгийн танхимд 'ХӨРӨГ' үзэсгэлэн гаргалаа.\n\nШилдэг бүтээлийн эзнээр ХГД 203-р бүлгийн суралцагч Б.Цагаанбаатар шалгарч Тэргүүн байр эзэллээ.",
                    "/static/news_horog.png",
                    "2020-10-30"
                )
            ]
            cur.executemany("""
                INSERT INTO news (title, category, summary, content, image, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, official_school_news)

        # Багш, удирдлагын анхны бодит өгөгдөл
        cur.execute("SELECT COUNT(*) FROM teachers")
        if cur.fetchone()[0] == 0:
            sample_teachers = [
                (
                    "Л. Болортуяа",
                    "Сургуулийн захирал",
                    "Боловсрол судлалын магистр · Тэргүүлэх багш · Боловсролын тэргүүний ажилтан",
                    "Удирдлага",
                    "18 жил",
                    "Мэргэжлийн боловсрол, сургалтын менежмент, чадамжид суурилсан сургалтын тогтолцоог хөгжүүлэхэд үнэтэй хувь нэмэр оруулж буй туршлагатай удирдагч.",
                    "bolortuya@ikhzasag.edu.mn",
                    "7711-9696",
                    "/static/bolortuya.png"
                ),
                (
                    "Д. Даваадорж",
                    "Сургалтын албаны дарга, зөвлөх багш",
                    "Дэд профессор · Боловсролын тэргүүний ажилтан",
                    "Удирдлага",
                    "22 жил",
                    "Чадамжид суурилсан сургалтын хөтөлбөр төлөвлөлт, хичээлийн стандарт, сургалтын чанарын дотоод баталгаажуулалтыг хариуцан ажилладаг.",
                    "davaadorj@ikhzasag.edu.mn",
                    "7015-7765",
                    "/static/davaadorj.png"
                ),
                (
                    "Б. Доржханд",
                    "Профессорын багийн ахлагч",
                    "Доктор (Ph.D) · Дэд профессор",
                    "Удирдлага",
                    "19 жил",
                    "Мэргэжлийн боловсролын судалгаа, заах арга зүй, багшийн тасралтгүй хөгжлийн хөтөлбөрийг удирдан чиглүүлдэг.",
                    "dorjkhand@ikhzasag.edu.mn",
                    "7711-9696",
                    "/static/teacher_dorjkhand.png"
                ),
                (
                    "А. Ганцэцэг",
                    "Мэргэжлийн хөтөлбөрийн удирдагч",
                    "Магистр · Ахлах багш",
                    "Мэргэжлийн тэнхим",
                    "14 жил",
                    "17 мэргэжлийн хөтөлбөрийн үйлдвэрлэлийн дадлага, ур чадварын үнэлгээ болон гэрээт аж ахуйн нэгжүүдтэй хамтын ажиллагааг хариуцдаг.",
                    "gantsetseg@ikhzasag.edu.mn",
                    "7015-7765",
                    "/static/teacher_gantsetseg.png"
                ),
                (
                    "Н. Оюунгэрэл",
                    "Ерөнхий эрдмийн тэнхимийн эрхлэгч",
                    "Магистр · Тэргүүлэх зэрэгтэй багш",
                    "Ерөнхий эрдмийн тэнхим",
                    "15 жил",
                    "9-р анги суурьтай элсэгчдийн бүрэн дунд боловсролын цөм хөтөлбөр, ерөнхий эрдмийн сургалтын чанарыг хариуцан ажилладаг.",
                    "oyungerel@ikhzasag.edu.mn",
                    "7711-9696",
                    "/static/teacher_oyungerel.png"
                ),
                (
                    "Г. Тэмүүлэн",
                    "График дизайн, Вэб хөгжүүлэлтийн багш",
                    "Мэдээллийн технологийн магистр · Зөвлөх багш",
                    "Мэргэжлийн тэнхим",
                    "11 жил",
                    "Adobe Creative Cloud, хэвлэлийн эх бэлтгэл, UI/UX дизайн болон орчин үеийн вэб технологийн хичээлүүдийг заадаг.",
                    "temuulen@ikhzasag.edu.mn",
                    "7015-7765",
                    "/static/teacher_temuulen.png"
                ),
                (
                    "Ц. Энхтуяа",
                    "Хоол үйлдвэрлэл, технологийн багш",
                    "Мастер тогооч · Тэргүүлэх багш",
                    "Мэргэжлийн тэнхим",
                    "18 жил",
                    "Ази, Европ хоолны технологи, нарийн боовны урлаг, нийтийн хоолны эрүүл ахуй, стандартын мэргэшсэн багш.",
                    "enkhtuya@ikhzasag.edu.mn",
                    "7015-7765",
                    "/static/teacher_enkhtuya.png"
                ),
                (
                    "С. Сарангэрэл",
                    "Хувцас дизайн, загвар зохион бүтээлтийн багш",
                    "Дизайны магистр · Ахлах багш",
                    "Мэргэжлийн тэнхим",
                    "12 жил",
                    "Үндэсний болон орчин үеийн хувцасны загвар зохион бүтээлт, эсгүүр, оёдлын технологийн хичээлүүдийг удирдан явуулдаг.",
                    "sarangerel@ikhzasag.edu.mn",
                    "7711-9696",
                    "/static/teacher_sarangerel.png"
                ),
                (
                    "П. Мөнх-Эрдэнэ",
                    "Оюутны хөгжил, нийгмийн ажилтан",
                    "Нийгмийн ажлын магистр",
                    "Оюутны алба",
                    "8 жил",
                    "Оюутны зөвлөл, урлаг спортын дугуйлан клубууд, дотуур байр болон төрөөс олгох 200,000₮ тэтгэлгийн бүртгэл мэдээллийг хариуцдаг.",
                    "munkherdene@ikhzasag.edu.mn",
                    "7711-9696",
                    "/static/teacher_munkherdene.png"
                )
            ]
            cur.executemany("""
                INSERT INTO teachers (name, role, degree, department, experience_years, bio, email, phone, photo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, sample_teachers)

        # Албан ёсны ikhzasag.edu.mn/schools/ikh-zasag-politekhnik-kollezh дээрх нэмэлт багш, ажилтнуудыг нэмэх
        cur.execute("SELECT COUNT(*) FROM teachers WHERE name IN ('Х. Оюун-Эрдэнэ', 'И. Нямсүрэн')")
        if cur.fetchone()[0] == 0:
            extra_official_teachers = [
                (
                    "Х. Оюун-Эрдэнэ",
                    "Захирлын туслах",
                    "Бизнесийн удирдлагын магистр",
                    "Удирдлага",
                    "9 жил",
                    "Коллежийн өдөр тутмын захиргааны үйл ажиллагаа, албан хэрэг хөтлөлт, удирдлагын зохион байгуулалтыг хариуцан ажилладаг.",
                    "oyunerdene@ikhzasag.edu.mn",
                    "7711-9696",
                    "/static/teacher_oyunerdene.png"
                ),
                (
                    "И. Нямсүрэн",
                    "Мэдээлэл технологийн ажилтан",
                    "Мэдээллийн технологийн инженер",
                    "Мэргэжлийн тэнхим",
                    "7 жил",
                    "Коллежийн компьютерийн лабораториуд, дотоод сүлжээ, цахим сургалтын систем болон техник хангамжийн хэвийн ажиллагааг хариуцдаг.",
                    "nyamsuren@ikhzasag.edu.mn",
                    "7015-7765",
                    "/static/teacher_nyamsuren.png"
                )
            ]
            cur.executemany("""
                INSERT INTO teachers (name, role, degree, department, experience_years, bio, email, phone, photo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, extra_official_teachers)

        # Одоо байгаа college.db доторх захирал (ID=1 -> Л. Болортуяа, ID=2 -> Д. Даваадорж) болон бүх багш нарын бодит зургийг шинэчлэх
        cur.execute("""
            UPDATE teachers
            SET name = 'Л. Болортуяа',
                role = 'Сургуулийн захирал',
                degree = 'Боловсрол судлалын магистр · Тэргүүлэх багш · Боловсролын тэргүүний ажилтан',
                department = 'Удирдлага',
                experience_years = '18 жил',
                bio = 'Мэргэжлийн боловсрол, сургалтын менежмент, чадамжид суурилсан сургалтын тогтолцоог хөгжүүлэхэд үнэтэй хувь нэмэр оруулж буй туршлагатай удирдагч.',
                email = 'bolortuya@ikhzasag.edu.mn',
                phone = '7711-9696',
                photo = '/static/bolortuya.png?v=2'
            WHERE id = 1
        """)
        cur.execute("""
            UPDATE teachers
            SET name = 'Д. Даваадорж',
                role = 'Сургалтын албаны дарга, зөвлөх багш',
                degree = 'Дэд профессор · Боловсролын тэргүүний ажилтан',
                department = 'Удирдлага',
                experience_years = '22 жил',
                bio = 'Чадамжид суурилсан сургалтын хөтөлбөр төлөвлөлт, хичээлийн стандарт, сургалтын чанарын дотоод баталгаажуулалтыг хариуцан ажилладаг.',
                email = 'davaadorj@ikhzasag.edu.mn',
                phone = '7015-7765',
                photo = '/static/davaadorj.png'
            WHERE id = 2
        """)
        cur.execute("UPDATE teachers SET photo = '/static/bolortuya.png?v=2' WHERE name = 'Л. Болортуяа'")
        teacher_photos = [
            ("/static/bolortuya.png?v=2", "Л. Болортуяа"),
            ("/static/davaadorj.png", "Д. Даваадорж"),
            ("/static/teacher_dorjkhand.png", "Б. Доржханд"),
            ("/static/teacher_gantsetseg.png", "А. Ганцэцэг"),
            ("/static/teacher_oyungerel.png", "Н. Оюунгэрэл"),
            ("/static/teacher_temuulen.png", "Г. Тэмүүлэн"),
            ("/static/teacher_enkhtuya.png", "Ц. Энхтуяа"),
            ("/static/teacher_sarangerel.png", "С. Сарангэрэл"),
            ("/static/teacher_munkherdene.png", "П. Мөнх-Эрдэнэ"),
            ("/static/teacher_oyunerdene.png", "Х. Оюун-Эрдэнэ"),
            ("/static/teacher_nyamsuren.png", "И. Нямсүрэн"),
        ]
        for photo_path, t_name in teacher_photos:
            cur.execute("UPDATE teachers SET photo = ? WHERE name = ? AND (photo IS NULL OR photo = '' OR photo LIKE '/static/%')", (photo_path, t_name))

        # Эвдэрсэн Unsplash зурагтай 2-р мэдээний зургийг засах
        cur.execute("UPDATE news SET image = 'https://images.unsplash.com/photo-1517486808906-6ca8b3f04846?auto=format&fit=crop&w=800&q=80' WHERE image LIKE '%photo-1523050854058%'")

        # 17 Мэргэжлийн анхны бодит өгөгдөл
        cur.execute("SELECT COUNT(*) FROM majors")
        if cur.fetchone()[0] == 0:
            sample_majors = [
                ("Хэвлэлийн график дизайнер", "design", "Дизайн", "3 жил", "9-р анги", "Сар бүр 200,000₮", "Мэргэжлийн диплом + Бүрэн дунд боловсрол", "ИЗОУИС-ийн 2-р курст шууд дэвших", "Adobe Photoshop, Illustrator, InDesign зэрэг мэргэжлийн программууд дээр хэвлэлийн эх бэлтгэл, лого брендинг, реклам сурталчилгааны дизайн бүтээх ур чадвар эзэмшинэ.", "Хэвлэлийн компани, маркетингийн агентлаг, телевиз, дизайн студид график дизайнер", 1),
                ("Хувцас дизайнч", "design", "Дизайн", "3 жил", "9-р анги", "Сар бүр 200,000₮", "Мэргэжлийн диплом + Бүрэн дунд боловсрол", "ИЗОУИС-ийн 2-р курст шууд дэвших", "Үндэсний болон орчин үеийн хувцасны эскиз зураг гаргах, эсгүүр хийх, загварчлах болон оёдлын технологийн цогц чадамж эзэмшинэ.", "Загварын салон, оёдлын үйлдвэр, хувийн урланд хувцасны дизайнер", 1),
                ("Хувцасны загвар зохион бүтээгч", "design", "Дизайн", "3 жил", "9-р анги", "Сар бүр 200,000₮", "Мэргэжлийн диплом + Бүрэн дунд боловсрол", "ИЗОУИС-ийн 2-р курст шууд дэвших", "Хувцасны суурь үлгэр байгуулах, технологийн карт боловсруулах, коллекц гаргах болон үйлдвэрлэлийн дамжлагыг удирдах ур чадвар олгоно.", "Хувцас загварын агентлаг, оёмол бүтээгдэхүүний үйлдвэрт зохион бүтээгч", 0),
                ("Тайз дэлгэцийн дизайн технологи", "design", "Дизайн", "3 жил", "9-р анги", "Сар бүр 200,000₮", "Мэргэжлийн диплом + Бүрэн дунд боловсрол", "ИЗОУИС-ийн 2-р курст шууд дэвших", "Театр, кино, телевизийн тайз засал, гэрэлтүүлэг, жижиг хэрэглэл болон дэлгэцийн зураг төслийг гүйцэтгэх бүтээлч мэргэжилтэн бэлтгэнэ.", "Телевиз, кино студи, театр, энтертайнмент продакшнд тайзны дизайнер", 0),
                ("Оёмол бүтээгдэхүүн үйлдвэрлэл", "design", "Дизайн", "1.5 жил", "12-р анги", "Тэтгэлэг болон хөнгөлөлттэй", "Техникийн боловсролын диплом", "ИЗОУИС-ийн 2-р курст шууд дэвших", "Бүрэн дунд боловсролтой элсэгчдэд богино хугацаанд оёдлын үйлдвэрлэлийн технологи, стандарт, тоног төхөөрөмжийн ашиглалтыг эзэмшүүлнэ.", "Оёдлын үйлдвэр, ноос ноолуурын компанид технологич, мастер", 0),
                ("Хоолны үйлчилгээ", "service", "Үйлчилгээ", "3 жил", "9-р анги", "Сар бүр 200,000₮", "Мэргэжлийн диплом + Бүрэн дунд боловсрол", "ИЗОУИС-ийн 2-р курст шууд дэвших", "Олон улсын стандартын дадлагын гал тогоонд Монгол, Ази, Европ хоол болон нарийн боов хийх технологи, хоолны газрын зохион байгуулалтыг судална.", "Зочид буудал, ресторан, амралтын газар, катеринг компанид мэргэжлийн тогооч", 1),
                ("Гоо сайхны үйлчилгээ", "service", "Үйлчилгээ", "3 жил", "9-р анги", "Сар бүр 200,000₮", "Мэргэжлийн диплом + Бүрэн дунд боловсрол", "ИЗОУИС-ийн 2-р курст шууд дэвших", "Арьс арчилгаа, нүүр будалт (Make-up), маникюр, педикюр, спа болон гоо заслын орчин үеийн аппарат тоног төхөөрөмж дээр ажиллах чадвар эзэмшинэ.", "Гоо сайхны салон, спа төв, телевиз студид гоо засалч, артист", 0),
                ("Үсчин, гоо сайхан", "service", "Үйлчилгээ", "1+1 жил", "9 ба 12-р анги", "Дадлага болон тэтгэлэгтэй", "Мэргэжлийн диплом", "Гадаад, дотоодын салонд ажиллах", "Эрэгтэй, эмэгтэй үс засалт, будалт, хими, гоёлын засалт болон гоо сайхны цогц үйлчилгээний практик ур чадварыг эзэмшүүлнэ.", "Үсчин гоо сайхны салон, хувийн бизнес эрхлэгч", 0),
                ("Аялал жуулчлалын 1+1 хөтөлбөр", "service", "Үйлчилгээ", "1+1 жил", "12-р анги", "БНСУ-д цалинтай дадлага", "Монгол болон БНСУ-ын хос диплом", "БНСУ-ын Кён-Ин Их Сургууль", "Монголд 1 жил, БНСУ-ын Кён-Ин коллежид 1 жил суралцан Солонгос хэл болон олон улсын аялал жуулчлалын менежментийн хос дипломтой төгсөнө.", "Олон улсын аялал жуулчлалын компани, нисэх буудал, гадаадын зочид буудал", 0),
                ("Аялал жуулчлалын үйлчилгээ", "service", "Үйлчилгээ", "3 жил", "9-р анги", "Сар бүр 200,000₮", "Мэргэжлийн диплом + Бүрэн дунд боловсрол", "ИЗОУИС-ийн 2-р курст шууд дэвших", "Аяллын хөтөч тайлбарлагч, тур оператор, жуулчны баазын үйлчилгээ, гадаад хэлний харилцааны өндөр ур чадвар эзэмшинэ.", "Жуулчны компани, ресорт, музей, соёлын төвд хөтөч, менежер", 0),
                ("Зочид буудал, зоогийн газрын үйлчилгээ", "service", "Үйлчилгээ", "3 жил", "9-р анги", "Сар бүр 200,000₮", "Мэргэжлийн диплом + Бүрэн дунд боловсрол", "ИЗОУИС-ийн 2-р курст шууд дэвших", "Олон улсын таван одтой зочид буудал, зоогийн газрын угтах үйлчилгээ, бариста, бартендер, зочин хүлээн авалтын стандартыг эзэмшинэ.", "Олон улсын сүлжээ зочид буудал, ресторанд зохион байгуулагч", 0),
                ("Барилгын сантехник, хоолой угсралт", "service", "Үйлчилгээ", "3 жил", "9-р анги", "Сар бүр 200,000₮", "Мэргэжлийн диплом + Бүрэн дунд боловсрол", "ИЗОУИС-ийн Инженерийн ангид дэвших", "Орчин үеийн барилга байгууламжийн халаалт, цэвэр бохир усны систем, агаар сэлгэлтийн шугам хоолойн угсралт, засвар үйлчилгээг гүйцэтгэж сурна.", "Барилга угсралтын компани, ОСНААК, инженерийн байгууллагад сантехникч", 0),
                ("Сувилагчийн туслах", "health", "Эрүүл мэнд", "3 жил", "9-р анги", "Сар бүр 200,000₮", "Мэргэжлийн диплом + Бүрэн дунд боловсрол", "ИЗОУИС-ийн Анагаахын сургуульд дэвших", "Эмнэлгийн анхан шатны тусламж, өвчтөний асаргаа сувилгаа, эмнэлгийн багаж хэрэгслийн ариутгал, эрүүл мэндийн бүртгэлийн ур чадвар эзэмшинэ.", "Улсын болон хувийн эмнэлэг, сувилал, сэргээн засах төвд сувилагчийн туслах", 1),
                ("Нягтлан бодох бүртгэлийн туслах ажилтан", "business", "Бизнес", "3 жил", "9-р анги", "Сар бүр 200,000₮", "Мэргэжлийн диплом + Бүрэн дунд боловсрол", "ИЗОУИС-ийн Санхүүгийн 2-р курст дэвших", "Санхүүгийн анхан шатны баримт боловсруулах, цалин хөлс тооцоолох, татварын тайлан гаргах болон санхүүгийн программ дээр ажиллах чадвар олгоно.", "Аж ахуйн нэгж, банк санхүү, төрийн байгууллагад тооцооны нягтлан, нярав", 1),
                ("Оффис ба бичиг хэргийн ажил", "business", "Бизнес", "3 жил", "9-р анги", "Сар бүр 200,000₮", "Мэргэжлийн диплом + Бүрэн дунд боловсрол", "ИЗОУИС-ийн 2-р курст шууд дэвших", "Албан бичиг хөтлөлтийн стандарт, архивын удирдлага, оффис менежмент, компьютерийн хэрэглээний программуудыг төгс эзэмшинэ.", "Төрийн болон хувийн хэвшлийн байгууллагад оффис менежер, архив бичиг хэрэг", 0),
                ("Хүний нөөцийн менежмент", "business", "Бизнес", "3 жил", "9-р анги", "Сар бүр 200,000₮", "Мэргэжлийн диплом + Бүрэн дунд боловсрол", "ИЗОУИС-ийн Бизнесийн сургуульд дэвших", "Байгууллагын хүний нөөцийн бүрдүүлэлт, сонгон шалгаруулалт, хөдөлмөрийн харилцаа, албан тушаалын тодорхойлолт боловсруулах чадвар эзэмшинэ.", "Компани, байгууллагын хүний нөөцийн албанд мэргэжилтэн, рекрутер", 0),
                ("Вэб дизайн", "tech", "Технологи", "3 жил", "9-р анги", "Сар бүр 200,000₮", "Мэргэжлийн диплом + Бүрэн дунд боловсрол", "ИЗОУИС-ийн Программ хангамжийн 2-р курст дэвших", "HTML5, CSS3, JavaScript, React, Python болон UI/UX дизайны зарчмаар орчин үеийн вэбсайт, гар утасны аппликейшны загвар, систем хөгжүүлж сурна.", "Мэдээллийн технологийн компани, стартап, банк санхүүгийн байгууллагад вэб хөгжүүлэгч", 1)
            ]
            cur.executemany("""
                INSERT INTO majors (name, category, category_label, duration, base_edu, stipend, diploma, pathway, description, career, featured)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, sample_majors)

        # Албан ёсны ikhzasag.edu.mn/schools/ikh-zasag-politekhnik-kollezh дээрх нэмэлт мэргэжлүүдийг нэмэх
        cur.execute("SELECT COUNT(*) FROM majors WHERE name = 'Цахим тоног төхөөрөмжийн үйлчилгээний ажилтан'")
        if cur.fetchone()[0] == 0:
            extra_official_majors = [
                ("Цахим тоног төхөөрөмжийн үйлчилгээний ажилтан", "tech", "Технологи", "3 жил", "9-р анги", "Сар бүр 200,000₮", "Мэргэжлийн диплом + Бүрэн дунд боловсрол", "ИЗОУИС-ийн ҮИТС-ийн 2-р курст дэвших", "Компьютер, оффисын тоног төхөөрөмжийн угсралт, оношилгоо, засвар үйлчилгээ болон дотоод сүлжээний тохиргоо хийх практик ур чадвар эзэмшинэ.", "Мэдээллийн технологийн төв, компьютер засварын газар, байгууллагын IT инженер", 0),
                ("Жэсан 2+2 олон улсын хөтөлбөр", "business", "Бизнес", "2+2 жил", "12-р анги", "Гадаадад цалинтай дадлага", "Олон улсын хос диплом", "БНСУ болон гадаадын түнш их сургуулиуд", "Эхний 2 жил Их Засаг Политехник Коллежид, дараагийн 2 жил гадаадын түнш их сургуульд суралцан олон улсын зэрэг, дипломтой төгсөх хөтөлбөр.", "Олон улсын корпораци, гадаад худалдаа, аялал жуулчлал, бизнесийн байгууллага", 0),
                ("Барилгын засал чимэглэлч", "service", "Үйлчилгээ", "2.5–3 жил", "9 ба 12-р анги", "Сар бүр 200,000₮", "Мэргэжлийн боловсролын үнэмлэх, диплом", "ИЗОУИС-ийн Барилгын инженерийн ангид дэвших", "Барилгын дотор болон гадна засал чимэглэл, интерьер засал, орчин үеийн барилгын материалын технологи, стандартыг эзэмшинэ.", "Барилга угсралт, интерьер дизайны компанид засал чимэглэлч, бригадын ахлагч", 0),
                ("Худалдааны газрын ажилтан", "business", "Бизнес", "2.5–3 жил", "9 ба 12-р анги", "Сар бүр 200,000₮", "Мэргэжлийн боловсролын үнэмлэх, диплом", "ИЗОУИС-ийн Бизнес удирдлагын ангид дэвших", "Худалдаа үйлчилгээний зохион байгуулалт, бараа судлал, кассын систем, борлуулалтын менежмент болон хэрэглэгчийн үйлчилгээний стандарт эзэмшинэ.", "Супермаркет сүлжээ, худалдааны төв, дистрибьюшн компанид борлуулалтын менежер", 0)
            ]
            cur.executemany("""
                INSERT INTO majors (name, category, category_label, duration, base_edu, stipend, diploma, pathway, description, career, featured)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, extra_official_majors)

        # Түгээмэл асуулт хариултын анхны бодит өгөгдөл
        cur.execute("SELECT COUNT(*) FROM faqs")
        if cur.fetchone()[0] == 0:
            sample_faqs = [
                (
                    "9-р анги төгсөөд элсэж болох уу? ЭЕШ өгөх шаардлагатай юу?",
                    "Тийм, 9-р анги төгссөн суралцагчид суурь боловсролын гэрчилгээгээрээ шууд элсэн орно. ЭЕШ-ын оноо шаардагдахгүй. 3 жилийн хугацаанд суралцаад Бүрэн дунд боловсролын үнэмлэх (12-р ангийн гэрчилгээ) болон Мэргэжлийн боловсролын диплом зэрэг гардан авдаг."
                ),
                (
                    "Сар бүр олгогдох 200,000₮-ийн тэтгэлгийг хэрхэн авах вэ?",
                    "Монгол Улсын Засгийн газрын Мэргэжлийн боловсрол, сургалтыг дэмжих сангийн журмын дагуу 9-р анги төгсөж коллежид өдрөөр суралцаж буй бүх суралцагчдад сар бүр 200,000 төгрөгийн тэтгэлэг олгогддог. Сургуулийн сургалтын алба элсэгчдийг нэгдсэн журмаар бүртгэж системд хамруулдаг."
                ),
                (
                    "Коллежоо төгсөөд их сургуульд шууд дэвшин суралцаж болох уу?",
                    "Бүрэн боломжтой. Их Засаг Политехник Коллежийн төгсөгчид Чингис Хааны нэрэмжит Их Засаг Олон Улсын Их Сургуулийн холбогдох бакалаврын хөтөлбөрийн 2-р дамжаанд шууд шатлан суралцаж дээд боловсрол эзэмших эрхтэй бөгөөд сургалтын төлбөрийн хөнгөлөлт эдэлдэг."
                ),
                (
                    "Оюутны дотуур байр болон бусад нөхцөл ямар байдаг вэ?",
                    "Их Засаг цогцолборын дэргэдэх 400 гаруй ортой, өндөр хурдны интернэт, бие даан суралцах танхим, гал тогоо, халуун ус, 24 цагийн харуул хамгаалалт бүхий тохилог оюутны байранд хөдөө орон нутгийн суралцагчид хөнгөлөлттэй төлбөрөөр амьдрах бүрэн боломжтой."
                ),
                (
                    "Үйлдвэрлэлийн бодит дадлагыг хаана хийдэг вэ?",
                    "Сургуулийн орчин үеийн компьютер график, оёдлын урлан, хоол үйлдвэрлэлийн стандарт гал тогоонд эхний шатны дадлага хийгдэх ба 2, 3-р дамжаанд гэрээт 50 гаруй нэр хүндтэй аж ахуйн нэгж, компаниудад цалинтай бодит дадлага хийдэг."
                ),
                (
                    "Элсэлтийн бүртгэлд ямар бичиг баримт бүрдүүлэх вэ?",
                    "1. Суурь боловсролын гэрчилгээ (9-р анги) эсвэл Бүрэн дунд боловсролын үнэмлэх (12-р анги) эх хувиар\n2. Иргэний үнэмлэхийн хуулбар эсвэл Төрсний гэрчилгээний лавлагаа (E-Mongolia)\n3. Цээж зураг 3х4 хэмжээтэй 4 хувь\n4. Суралцагчийн хувийн хэрэг."
                )
            ]
            cur.executemany("INSERT INTO faqs (question, answer) VALUES (?, ?)", sample_faqs)

        conn.commit()


def get_site_settings():
    settings = dict(DEFAULT_SETTINGS)
    try:
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT key, value FROM site_settings").fetchall()
            for r in rows:
                settings[r["key"]] = r["value"]
    except Exception:
        pass
    return settings


_db_synced = False


@app.context_processor
def inject_global_data():
    global _db_synced
    if not _db_synced:
        init_db()
        _db_synced = True
    return {"site_settings": get_site_settings()}


# --- НИЙТИЙН ХУУДАСНЫ ROUTES ---

@app.route("/")
def home():
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        news_list = conn.execute("SELECT id, title, category, summary, content, image, created_at FROM news ORDER BY id DESC").fetchall()
        featured_majors = conn.execute("SELECT * FROM majors WHERE featured = 1 ORDER BY id ASC LIMIT 6").fetchall()
        if not featured_majors:
            featured_majors = conn.execute("SELECT * FROM majors ORDER BY id ASC LIMIT 6").fetchall()
        faqs = conn.execute("SELECT id, question, answer FROM faqs ORDER BY id ASC").fetchall()
        teachers = conn.execute("SELECT * FROM teachers ORDER BY id ASC LIMIT 4").fetchall()
    return render_template("index.html", news_list=news_list, featured_majors=featured_majors, faqs=faqs, teachers=teachers)


@app.route("/about")
def about():
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        teachers = conn.execute("SELECT * FROM teachers ORDER BY id ASC").fetchall()
        faqs = conn.execute("SELECT id, question, answer FROM faqs ORDER BY id ASC").fetchall()
        news_list = conn.execute("SELECT id, title, category, summary, content, image, created_at FROM news ORDER BY id DESC").fetchall()
    return render_template("about.html", teachers=teachers, faqs=faqs, news_list=news_list)


@app.route("/students")
def students():
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        majors = conn.execute("SELECT * FROM majors ORDER BY id ASC").fetchall()
    return render_template("students.html", majors=majors)


@app.route("/apply", methods=["GET", "POST"])
def apply():
    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        birthdate = request.form.get("birthdate", "").strip()
        if not birthdate:
            b_year = request.form.get("birth_year", "").strip()
            b_month = request.form.get("birth_month", "").strip()
            b_day = request.form.get("birth_day", "").strip()
            if b_year and b_month and b_day:
                birthdate = f"{b_year}-{b_month.zfill(2)}-{b_day.zfill(2)}"

        gender = request.form.get("gender", "").strip()
        major = request.form.get("major", "").strip()
        phone = request.form.get("phone", "").strip()

        if not all([fullname, birthdate, gender, major, phone]):
            flash("Бүх талбарыг бөглөнө үү.", "error")
            return redirect(url_for("apply"))

        clean_phone = "".join(filter(str.isdigit, phone))
        if len(clean_phone) != 8:
            flash("Утасны дугаараа 8 оронтой зөв тоо оруулна уу (Жишээ нь: 99112233).", "error")
            return redirect(url_for("apply"))

        try:
            with get_db() as conn:
                conn.execute("""
                    INSERT INTO applications 
                    (fullname, birthdate, gender, major, phone, status) 
                    VALUES (?, ?, ?, ?, ?, 'Шинэ')
                """, (fullname, birthdate, gender, major, clean_phone))
                conn.commit()
            flash(f"Баярлалаа, {fullname}! Таны элсэлтийн бүртгэл амжилттай хадгалагдлаа. Бид тантай удахгүй холбогдох болно.", "success")
        except Exception:
            flash("Бүртгэл хадгалахад алдаа гарлаа. Та дахин оролдоно уу.", "error")

        return redirect(url_for("apply"))

    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        majors = conn.execute("SELECT * FROM majors ORDER BY id ASC").fetchall()
    return render_template("apply.html", majors=majors)


# --- АДМИН НЭВТРЭХ БА ЕРӨНХИЙ САМБАР ---

@app.route("/admin")
def admin_root():
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "ihzasag2026":
            session["admin_logged"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Нэвтрэх нэр эсвэл нууц үг буруу байна.", "error")

    return render_template("admin_login.html")


@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        applications = conn.execute("""
            SELECT id, fullname, birthdate, gender, major, phone, status, notes, created_at
            FROM applications
            ORDER BY id DESC
        """).fetchall()
        news_list = conn.execute("""
            SELECT id, title, category, summary, content, image, created_at
            FROM news
            ORDER BY id DESC
        """).fetchall()
        teachers = conn.execute("""
            SELECT id, name, role, degree, department, experience_years, bio, email, phone, photo, created_at
            FROM teachers
            ORDER BY id ASC
        """).fetchall()
        majors = conn.execute("""
            SELECT id, name, category, category_label, duration, base_edu, stipend, diploma, pathway, description, career, featured, created_at
            FROM majors
            ORDER BY id ASC
        """).fetchall()
        faqs = conn.execute("""
            SELECT id, question, answer, created_at
            FROM faqs
            ORDER BY id ASC
        """).fetchall()

    return render_template(
        "admin_dashboard.html",
        applications=applications,
        news_list=news_list,
        teachers=teachers,
        majors=majors,
        faqs=faqs
    )


# --- 1. ЭЛСЭЛТИЙН БҮРТГЭЛИЙН УДИРДЛАГА ---

@app.route("/admin/export")
def admin_export():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Овог, нэр', 'Төрсөн огноо', 'Хүйс', 'Мэргэжил', 'Утас', 'Төлөв', 'Тэмдэглэл', 'Бүртгүүлсэн огноо'])

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, fullname, birthdate, gender, major, phone, status, notes, created_at FROM applications ORDER BY id DESC")
        for row in cursor.fetchall():
            writer.writerow(row)

    output.seek(0)
    return Response(
        '\ufeff' + output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=elseltiin_burtgel.csv"}
    )


@app.route("/admin/add", methods=["POST"])
def admin_add_application():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    fullname = request.form.get("fullname", "").strip()
    birthdate = request.form.get("birthdate", "").strip()
    if not birthdate:
        b_year = request.form.get("birth_year", "").strip()
        b_month = request.form.get("birth_month", "").strip()
        b_day = request.form.get("birth_day", "").strip()
        if b_year and b_month and b_day:
            birthdate = f"{b_year}-{b_month.zfill(2)}-{b_day.zfill(2)}"

    gender = request.form.get("gender", "").strip()
    major = request.form.get("major", "").strip()
    phone = request.form.get("phone", "").strip()
    status = request.form.get("status", "Шинэ").strip()
    notes = request.form.get("notes", "").strip()

    if not all([fullname, birthdate, gender, major, phone]):
        flash("Бүх талбарыг бүрэн бөглөнө үү.", "error")
        return redirect(url_for("admin_dashboard"))

    clean_phone = "".join(filter(str.isdigit, phone))
    if len(clean_phone) != 8:
        flash("Утасны дугаараа 8 оронтой зөв тоо оруулна уу.", "error")
        return redirect(url_for("admin_dashboard"))

    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO applications 
                (fullname, birthdate, gender, major, phone, status, notes) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (fullname, birthdate, gender, major, clean_phone, status, notes))
            conn.commit()
        flash(f"'{fullname}' суралцагчийн бүртгэл амжилттай нэмэгдлээ.", "success")
    except Exception:
        flash("Бүртгэл нэмэхэд алдаа гарлаа.", "error")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/edit/<int:id>", methods=["POST"])
def admin_edit_application(id):
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    fullname = request.form.get("fullname", "").strip()
    birthdate = request.form.get("birthdate", "").strip()
    if not birthdate:
        b_year = request.form.get("birth_year", "").strip()
        b_month = request.form.get("birth_month", "").strip()
        b_day = request.form.get("birth_day", "").strip()
        if b_year and b_month and b_day:
            birthdate = f"{b_year}-{b_month.zfill(2)}-{b_day.zfill(2)}"

    gender = request.form.get("gender", "").strip()
    major = request.form.get("major", "").strip()
    phone = request.form.get("phone", "").strip()
    status = request.form.get("status", "Шинэ").strip()
    notes = request.form.get("notes", "").strip()

    if not all([fullname, birthdate, gender, major, phone]):
        flash("Бүх талбарыг бүрэн бөглөнө үү.", "error")
        return redirect(url_for("admin_dashboard"))

    clean_phone = "".join(filter(str.isdigit, phone))
    if len(clean_phone) != 8:
        flash("Утасны дугаараа 8 оронтой зөв тоо оруулна уу.", "error")
        return redirect(url_for("admin_dashboard"))

    try:
        with get_db() as conn:
            conn.execute("""
                UPDATE applications 
                SET fullname = ?, birthdate = ?, gender = ?, major = ?, phone = ?, status = ?, notes = ?
                WHERE id = ?
            """, (fullname, birthdate, gender, major, clean_phone, status, notes, id))
            conn.commit()
        flash(f"ID #{id} бүртгэлийн мэдээлэл амжилттай шинэчлэгдлээ.", "success")
    except Exception:
        flash("Мэдээлэл засахад алдаа гарлаа.", "error")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete/<int:id>", methods=["POST", "GET"])
def delete_application(id):
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    with get_db() as conn:
        conn.execute("DELETE FROM applications WHERE id = ?", (id,))
        conn.commit()

    flash(f"ID #{id} бүртгэл амжилттай устгагдлаа.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete-selected", methods=["POST"])
def admin_delete_selected():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    selected_ids = request.form.getlist("selected_ids")
    if not selected_ids:
        flash("Устгах бүртгэл сонгогдоогүй байна.", "error")
        return redirect(url_for("admin_dashboard"))

    try:
        placeholders = ",".join("?" * len(selected_ids))
        with get_db() as conn:
            conn.execute(f"DELETE FROM applications WHERE id IN ({placeholders})", selected_ids)
            conn.commit()
        flash(f"Сонгогдсон {len(selected_ids)} бүртгэл амжилттай устгагдлаа.", "success")
    except Exception:
        flash("Бүртгэлүүдийг устгахад алдаа гарлаа.", "error")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/clear-all", methods=["POST"])
def admin_clear_all():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    try:
        with get_db() as conn:
            conn.execute("DELETE FROM applications")
            conn.commit()
        flash("Бүх бүртгэлийн өгөгдөл амжилттай цэвэрлэгдлээ.", "success")
    except Exception:
        flash("Өгөгдөл цэвэрлэхэд алдаа гарлаа.", "error")

    return redirect(url_for("admin_dashboard"))


# --- 2. БАГШ, УДИРДЛАГЫН УДИРДЛАГА (CRUD) ---

@app.route("/admin/teachers/add", methods=["POST"])
def admin_add_teacher():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    name = request.form.get("name", "").strip()
    role = request.form.get("role", "").strip()
    degree = request.form.get("degree", "").strip()
    department = request.form.get("department", "Мэргэжлийн тэнхим").strip()
    experience_years = request.form.get("experience_years", "").strip()
    bio = request.form.get("bio", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    photo_url = request.form.get("photo_url", "").strip()

    if not name or not role:
        flash("Багшийн овог нэр болон албан тушаалыг заавал оруулна уу.", "error")
        return redirect(url_for("admin_dashboard") + "?tab=teachers")

    uploaded_photo = save_uploaded_image("photo_file", prefix="teacher")
    photo_path = uploaded_photo if uploaded_photo else photo_url

    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO teachers (name, role, degree, department, experience_years, bio, email, phone, photo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, role, degree, department, experience_years, bio, email, phone, photo_path))
            conn.commit()
        flash(f"'{name}' багшийн мэдээлэл амжилттай нэмэгдлээ.", "success")
    except Exception as e:
        flash(f"Багш нэмэхэд алдаа гарлаа: {e}", "error")

    return redirect(url_for("admin_dashboard") + "?tab=teachers")


@app.route("/admin/teachers/edit/<int:id>", methods=["POST"])
def admin_edit_teacher(id):
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    name = request.form.get("name", "").strip()
    role = request.form.get("role", "").strip()
    degree = request.form.get("degree", "").strip()
    department = request.form.get("department", "Мэргэжлийн тэнхим").strip()
    experience_years = request.form.get("experience_years", "").strip()
    bio = request.form.get("bio", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    photo_url = request.form.get("photo_url", "").strip()

    if not name or not role:
        flash("Багшийн овог нэр болон албан тушаалыг заавал оруулна уу.", "error")
        return redirect(url_for("admin_dashboard") + "?tab=teachers")

    uploaded_photo = save_uploaded_image("photo_file", prefix="teacher")
    new_photo = uploaded_photo if uploaded_photo else (photo_url if photo_url else None)

    try:
        with get_db() as conn:
            if new_photo is not None:
                conn.execute("""
                    UPDATE teachers
                    SET name = ?, role = ?, degree = ?, department = ?, experience_years = ?, bio = ?, email = ?, phone = ?, photo = ?
                    WHERE id = ?
                """, (name, role, degree, department, experience_years, bio, email, phone, new_photo, id))
            else:
                conn.execute("""
                    UPDATE teachers
                    SET name = ?, role = ?, degree = ?, department = ?, experience_years = ?, bio = ?, email = ?, phone = ?
                    WHERE id = ?
                """, (name, role, degree, department, experience_years, bio, email, phone, id))
            conn.commit()
        flash(f"'{name}' багшийн мэдээлэл амжилттай шинэчлэгдлээ.", "success")
    except Exception as e:
        flash(f"Багшийн мэдээлэл засахад алдаа гарлаа: {e}", "error")

    return redirect(url_for("admin_dashboard") + "?tab=teachers")


@app.route("/admin/teachers/delete/<int:id>", methods=["POST", "GET"])
def admin_delete_teacher(id):
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    try:
        with get_db() as conn:
            conn.execute("DELETE FROM teachers WHERE id = ?", (id,))
            conn.commit()
        flash(f"ID #{id} багшийн бүртгэл устгагдлаа.", "success")
    except Exception as e:
        flash(f"Устгахад алдаа гарлаа: {e}", "error")

    return redirect(url_for("admin_dashboard") + "?tab=teachers")


# --- 3. СУРГАЛТЫН МЭРГЭЖИЛ, ХӨТӨЛБӨРИЙН УДИРДЛАГА (CRUD) ---

CATEGORY_LABELS = {
    "design": "Дизайн",
    "service": "Үйлчилгээ",
    "health": "Эрүүл мэнд",
    "business": "Бизнес",
    "tech": "Технологи"
}


@app.route("/admin/majors/add", methods=["POST"])
def admin_add_major():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    name = request.form.get("name", "").strip()
    category = request.form.get("category", "design").strip()
    category_label = CATEGORY_LABELS.get(category, "Дизайн")
    duration = request.form.get("duration", "3 жил").strip()
    base_edu = request.form.get("base_edu", "9-р анги").strip()
    stipend = request.form.get("stipend", "Сар бүр 200,000₮").strip()
    diploma = request.form.get("diploma", "Мэргэжлийн диплом + Бүрэн дунд боловсрол").strip()
    pathway = request.form.get("pathway", "ИЗОУИС-ийн 2-р курст шууд дэвших").strip()
    description = request.form.get("description", "").strip()
    career = request.form.get("career", "").strip()
    featured = 1 if request.form.get("featured") == "1" else 0

    if not name or not description:
        flash("Мэргэжлийн нэр болон тайлбарыг заавал оруулна уу.", "error")
        return redirect(url_for("admin_dashboard") + "?tab=majors")

    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO majors (name, category, category_label, duration, base_edu, stipend, diploma, pathway, description, career, featured)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, category, category_label, duration, base_edu, stipend, diploma, pathway, description, career, featured))
            conn.commit()
        flash(f"'{name}' мэргэжил амжилттай нэмэгдлээ.", "success")
    except Exception as e:
        flash(f"Мэргэжил нэмэхэд алдаа гарлаа: {e}", "error")

    return redirect(url_for("admin_dashboard") + "?tab=majors")


@app.route("/admin/majors/edit/<int:id>", methods=["POST"])
def admin_edit_major(id):
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    name = request.form.get("name", "").strip()
    category = request.form.get("category", "design").strip()
    category_label = CATEGORY_LABELS.get(category, "Дизайн")
    duration = request.form.get("duration", "3 жил").strip()
    base_edu = request.form.get("base_edu", "9-р анги").strip()
    stipend = request.form.get("stipend", "Сар бүр 200,000₮").strip()
    diploma = request.form.get("diploma", "Мэргэжлийн диплом + Бүрэн дунд боловсрол").strip()
    pathway = request.form.get("pathway", "ИЗОУИС-ийн 2-р курст шууд дэвших").strip()
    description = request.form.get("description", "").strip()
    career = request.form.get("career", "").strip()
    featured = 1 if request.form.get("featured") == "1" else 0

    if not name or not description:
        flash("Мэргэжлийн нэр болон тайлбарыг заавал оруулна уу.", "error")
        return redirect(url_for("admin_dashboard") + "?tab=majors")

    try:
        with get_db() as conn:
            conn.execute("""
                UPDATE majors
                SET name = ?, category = ?, category_label = ?, duration = ?, base_edu = ?, stipend = ?, diploma = ?, pathway = ?, description = ?, career = ?, featured = ?
                WHERE id = ?
            """, (name, category, category_label, duration, base_edu, stipend, diploma, pathway, description, career, featured, id))
            conn.commit()
        flash(f"'{name}' мэргэжлийн мэдээлэл шинэчлэгдлээ.", "success")
    except Exception as e:
        flash(f"Мэргэжил засахад алдаа гарлаа: {e}", "error")

    return redirect(url_for("admin_dashboard") + "?tab=majors")


@app.route("/admin/majors/delete/<int:id>", methods=["POST", "GET"])
def admin_delete_major(id):
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    try:
        with get_db() as conn:
            conn.execute("DELETE FROM majors WHERE id = ?", (id,))
            conn.commit()
        flash(f"ID #{id} мэргэжил устгагдлаа.", "success")
    except Exception as e:
        flash(f"Мэргэжил устгахад алдаа гарлаа: {e}", "error")

    return redirect(url_for("admin_dashboard") + "?tab=majors")


# --- 4. МЭДЭЭ, ЗАРЛАЛЫН УДИРДЛАГА (CRUD) ---

@app.route("/admin/news/add", methods=["POST"])
def admin_add_news():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    title = request.form.get("title", "").strip()
    category = request.form.get("category", "Зарлал").strip()
    summary = request.form.get("summary", "").strip()
    content = request.form.get("content", "").strip()
    image_url = request.form.get("image_url", "").strip()

    if not title or not summary:
        flash("Мэдээний гарчиг болон товч агуулгыг заавал оруулна уу.", "error")
        return redirect(url_for("admin_dashboard") + "?tab=news")

    if not content:
        content = summary

    uploaded_img = save_uploaded_image("image_file", prefix="news")
    image_path = uploaded_img if uploaded_img else image_url

    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO news (title, category, summary, content, image)
                VALUES (?, ?, ?, ?, ?)
            """, (title, category, summary, content, image_path))
            conn.commit()
        flash(f"'{title}' мэдээ амжилттай нийтлэгдэж, вэбсайт дээр гарлаа!", "success")
    except Exception as e:
        flash(f"Мэдээ нийтлэхэд алдаа гарлаа: {e}", "error")

    return redirect(url_for("admin_dashboard") + "?tab=news")


@app.route("/admin/news/edit/<int:id>", methods=["POST"])
def admin_edit_news(id):
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    title = request.form.get("title", "").strip()
    category = request.form.get("category", "Зарлал").strip()
    summary = request.form.get("summary", "").strip()
    content = request.form.get("content", "").strip()
    image_url = request.form.get("image_url", "").strip()

    if not title or not summary:
        flash("Мэдээний гарчиг болон товч агуулгыг заавал оруулна уу.", "error")
        return redirect(url_for("admin_dashboard") + "?tab=news")

    if not content:
        content = summary

    uploaded_img = save_uploaded_image("image_file", prefix="news")
    new_image = uploaded_img if uploaded_img else (image_url if image_url else None)

    try:
        with get_db() as conn:
            if new_image is not None and new_image != "":
                conn.execute("""
                    UPDATE news
                    SET title = ?, category = ?, summary = ?, content = ?, image = ?
                    WHERE id = ?
                """, (title, category, summary, content, new_image, id))
            else:
                conn.execute("""
                    UPDATE news
                    SET title = ?, category = ?, summary = ?, content = ?
                    WHERE id = ?
                """, (title, category, summary, content, id))
            conn.commit()
        flash(f"ID #{id} мэдээ амжилттай шинэчлэгдлээ.", "success")
    except Exception as e:
        flash(f"Мэдээ засварлахад алдаа гарлаа: {e}", "error")

    return redirect(url_for("admin_dashboard") + "?tab=news")


@app.route("/admin/news/delete/<int:id>", methods=["POST", "GET"])
def admin_delete_news(id):
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    try:
        with get_db() as conn:
            conn.execute("DELETE FROM news WHERE id = ?", (id,))
            conn.commit()
        flash(f"ID #{id} мэдээ амжилттай устгагдлаа.", "success")
    except Exception as e:
        flash(f"Мэдээ устгахад алдаа гарлаа: {e}", "error")

    return redirect(url_for("admin_dashboard") + "?tab=news")


# --- 5. ТҮГЭЭМЭЛ АСУУЛТ ХАРИУЛТЫН УДИРДЛАГА (FAQ CRUD) ---

@app.route("/admin/faqs/add", methods=["POST"])
def admin_add_faq():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    question = request.form.get("question", "").strip()
    answer = request.form.get("answer", "").strip()

    if not question or not answer:
        flash("Асуулт болон хариултыг заавал бөглөнө үү.", "error")
        return redirect(url_for("admin_dashboard") + "?tab=faqs")

    try:
        with get_db() as conn:
            conn.execute("INSERT INTO faqs (question, answer) VALUES (?, ?)", (question, answer))
            conn.commit()
        flash("Түгээмэл асуулт амжилттай нэмэгдлээ.", "success")
    except Exception as e:
        flash(f"Асуулт нэмэхэд алдаа гарлаа: {e}", "error")

    return redirect(url_for("admin_dashboard") + "?tab=faqs")


@app.route("/admin/faqs/edit/<int:id>", methods=["POST"])
def admin_edit_faq(id):
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    question = request.form.get("question", "").strip()
    answer = request.form.get("answer", "").strip()

    if not question or not answer:
        flash("Асуулт болон хариултыг заавал бөглөнө үү.", "error")
        return redirect(url_for("admin_dashboard") + "?tab=faqs")

    try:
        with get_db() as conn:
            conn.execute("UPDATE faqs SET question = ?, answer = ? WHERE id = ?", (question, answer, id))
            conn.commit()
        flash(f"ID #{id} асуулт хариулт шинэчлэгдлээ.", "success")
    except Exception as e:
        flash(f"Асуулт засахад алдаа гарлаа: {e}", "error")

    return redirect(url_for("admin_dashboard") + "?tab=faqs")


@app.route("/admin/faqs/delete/<int:id>", methods=["POST", "GET"])
def admin_delete_faq(id):
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    try:
        with get_db() as conn:
            conn.execute("DELETE FROM faqs WHERE id = ?", (id,))
            conn.commit()
        flash(f"ID #{id} асуулт устгагдлаа.", "success")
    except Exception as e:
        flash(f"Асуулт устгахад алдаа гарлаа: {e}", "error")

    return redirect(url_for("admin_dashboard") + "?tab=faqs")


# --- 6. САЙТЫН ЕРӨНХИЙ ТОХИРГОО ХАДГАЛАХ ---

@app.route("/admin/settings/save", methods=["POST"])
def admin_save_settings():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    try:
        with get_db() as conn:
            for key in DEFAULT_SETTINGS.keys():
                if key in request.form:
                    val = request.form.get(key, "").strip()
                    conn.execute("INSERT OR REPLACE INTO site_settings (key, value) VALUES (?, ?)", (key, val))
            conn.commit()
        flash("Сайтын ерөнхий мэдээлэл болон статистик амжилттай хадгалагдлаа!", "success")
    except Exception as e:
        flash(f"Тохиргоо хадгалахад алдаа гарлаа: {e}", "error")

    return redirect(url_for("admin_dashboard") + "?tab=settings")


@app.route("/logout")
@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged", None)
    return redirect(url_for("home"))


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
