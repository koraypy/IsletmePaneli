# İşletme Paneli

İşletmenizin tüm bilgilerini (personel, müşteri, tedarikçi, araç, belge… ne isterseniz) **kendi bilgisayarınızda** tek yerde toplayan, tek bir arama kutusuyla her şeyi bulduran, **internet ve abonelik gerektirmeyen** Windows masaüstü uygulaması.

- Veriler yalnızca sizin bilgisayarınızdaki bir SQLite dosyasında durur (buluta gönderilmez).
- Hiçbir ek paket gerekmez: yalnızca Python standart kütüphanesi (Tkinter + SQLite).
- Lisans: MIT — ücretsiz, değiştirilebilir, paylaşılabilir.

## Özellikler

| | |
|---|---|
| 🔎 **Tek kutudan arama** | Ad, telefon, TC, plaka… neyi yazarsanız tüm kategorilerde arar. Büyük/küçük harf, Türkçe karakter (ı/i, ş/s…), yazım hatası ve boşluklu telefon (`0555 444 55 44`) fark etmez. |
| 🗂️ **Özelleştirilebilir kategoriler** | Kategori ekle / sil / yeniden adlandır. Her kategoride istediğiniz alanı ekleyip çıkarın, sırasını değiştirin. Kod yazmaya gerek yok. |
| 🔒 **Gizli alanlar** | TC, IBAN gibi alanlar ekranda `•••` görünür; “Göster” ile açılır. Yapay zekâya hiçbir zaman gönderilmez. |
| ✨ **Akıllı sor** | `Ahmet'in telefonu` yazıp Enter → doğrudan yanıt verir (çevrimdışı, ücretsiz). |
| ⚡ **Hızlı ekleme** | Arama kutusuna `+ Personel | Mehmet Kaya | 0532 111 22 33` yazıp Enter → kayıt hazır. |
| 🎨 **Görünüm** | Açık/koyu tema, vurgu rengi, yazı boyutu. Ayarlar hatırlanır. |
| 💾 **Yedek** | Her gün otomatik yedek (son 14 gün), elle yedek, JSON/CSV(Excel) dışa aktarma, JSON içe aktarma, kayıtsız şablon dışa aktarma. |
| 📋 **Kopyala** | Her alanın yanında tek tıkla panoya kopyalama. |
| 💬 **WhatsApp mesajı** | Kayıtlı numaradan tek tıkla WhatsApp'ı hazır mesajla açar; tek kişiye ya da listelenen herkese sırayla. Şablonlar ve `{ad}` gibi kişiye özel alanlar. |
| 🔄 **Güncelleme** | GitHub'daki yeni sürümü denetler; `.exe` sürümünde tek tıkla indirip kurar (SHA256 doğrulamalı). Verileriniz korunur. |
| 🌐 **Web formu (PHP)** | Personel telefonundan bir bağlantıyla kendi bilgisini girer; panel başvuruları çeker, “yeni / zaten kayıtlı / bilgisi farklı” diye ayırır, onayınızla ekler ve sunucudan siler. Ücretsiz hostta çalışır. Kurulum: [`web/KURULUM.md`](web/KURULUM.md). |
| 📥 **Excel/CSV karşılaştırma + izleme** | Elinizdeki listeyi panelle karşılaştırır: kim **yeni**, kimin bilgisi **değişmiş**, kim **listede yok**. Dosyayı izleyip değişince haber verir. |

Uygulama ilk açıldığında **Personel / Müşteri / Tedarikçi** kategorileri ve örnek bir personel kaydı (*Ahmet Yalın*) ile gelir. Örneği silmek için kaydı seçip **Sil**'e basmanız yeterli.

## Kurulum

### 1) Hazır .exe (önerilen)
GitHub'da **Releases** sayfasından `IsletmePaneli.exe` dosyasını indirip çift tıklayın. Kurulum gerekmez.

> Windows SmartScreen / antivirüs, imzasız ve PyInstaller ile üretilmiş `.exe` dosyalarına ilk çalıştırmada uyarı verebilir. Kaynak kodu bu depoda açıktır; isterseniz kendiniz derleyebilirsiniz.

### 2) Kaynak koddan çalıştırma
1. [Python 3.9+](https://www.python.org/downloads/) kurun (Windows kurulumu Tkinter'ı içerir).
2. `run.bat` dosyasına çift tıklayın veya `python app.py` çalıştırın.

### 3) Kendi .exe dosyanızı üretme
`build.bat` dosyasına çift tıklayın → `dist\IsletmePaneli.exe` oluşur.

### 4) GitHub ile otomatik .exe
Depoyu GitHub'a yükleyin. **Actions ▸ Windows .exe derle ▸ Run workflow** deyin ya da bir etiket (tag) gönderin:

```
git tag v1.0.0
git push origin v1.0.0
```
Derlenen `.exe` hem Actions çıktısında hem de **Releases** sayfasında görünür.

## Listeyi panelle karşılaştırma (Excel / CSV)

Düzen ▸ **Dosyadan karşılaştır / içe aktar**:

1. Kategoriyi ve `.xlsx` / `.csv` dosyasını seçin (eski `.xls` ise Excel'de `.xlsx` olarak kaydedin).
2. Dosyadaki sütunları panelin alanlarıyla eşleştirin (adlar benziyorsa otomatik eşleşir). Kişiler **telefon** ile tanınır.
3. **Karşılaştır**'a basın. Sonuç sekmeleri: **Yeni** · **Değişmiş** · **Listede yok** · **Aynı** · **Sorunlu**.
4. Sekmelerden seçilileri/hepsini ekleyin ya da güncelleyin. Onay vermeden hiçbir şey değişmez; dosyada boş olan hücre paneldeki bilgiyi silmez; “Listede yok” kişiler silinmez.

Telefon eşleştirmesi son 10 haneye bakar; `0555 444 55 44`, `+90 555 444 55 44` ve Excel'in baştaki 0'ı attığı `5554445544` aynı numara sayılır. Bir hücrede birden fazla numara varsa (`0555… / 0532…`) hepsi denenir. Telefonu olmayan satırlar ve dosyada tekrar eden numaralar **Sorunlu** sekmesinde ayrıca gösterilir.

**İzleme (bot):** “Bu dosyayı izle” kutusunu işaretleyip Karşılaştır'a basarsanız panel, belirlediğiniz aralıkta (varsayılan 30 dk) dosyanın değişip değişmediğine bakar. Değişmişse ve yeni/değişen kişi varsa “3 yeni kişi var” diye sorar, onaylarsanız karşılaştırma ekranı hazır gelir. Panel kapalıyken kontrol yapılmaz; açıldığında ilk iş kontrol eder. Dosya Excel'de açıksa okunamayabilir, sonraki turda yeniden denenir.

## Web formu ile personel bilgisi toplama

`web/` klasörü, ücretsiz PHP hostuna yükleyeceğiniz küçük bir sitedir (form + panel için API). Adım adım kurulum, güvenlik önlemleri ve KVKK notları: **[web/KURULUM.md](web/KURULUM.md)**.
Panel tarafı: Ayarlar ▸ *Web formu* (adres, anahtar, davet kodu) ve Dosya ▸ **Web başvuruları**. TC kimlik no gibi hassas veriyi web formundan toplamamanızı öneririz.

## WhatsApp'tan mesaj gönderme

- **Tek kişi:** kaydı seçin ▸ **💬 WhatsApp**. **Toplu:** arama yapın ya da bir kategori seçin ▸ üstteki **💬 Toplu mesaj** (listelenen herkes).
- Mesajı yazın ya da şablon seçin. `{ad}` (ilk ad), `{tam_ad}` ve kategorinizdeki alan adları (`{görev}` gibi) kişiye göre otomatik dolar. **Gizli alanlar (TC, IBAN) mesaja hiçbir zaman konmaz.** Beğendiğiniz mesajı **Kaydet** ile şablon yapın.
- **Seçiliyi WhatsApp'ta aç** ya da toplu listede **Sıradakini aç →**: WhatsApp mesaj hazır şekilde açılır, **Gönder'e siz basarsınız**. Her kişi “açıldı ✓” olarak işaretlenir.
- Numaralar otomatik düzeltilir (`0555…`, `+90 555…`, `555…` → uluslararası biçim). Sabit hatlar atlanır. Bir kayıtta birden fazla numara varsa seçebilirsiniz.
- Ayarlar'dan açma yöntemini seçin: tarayıcı (wa.me, her zaman çalışır) ya da WhatsApp Masaüstü uygulaması.

**Neden otomatik gönderilmiyor?** Kullanıcı onayı olmadan otomatik gönderim yalnızca resmî *WhatsApp Business Platform (Cloud API)* ile mümkündür: Meta işletme doğrulaması, onaylı şablonlar ve konuşma başına ücret gerektirir. Resmî olmayan otomasyonlar (tarayıcı botları vb.) WhatsApp şartlarına aykırıdır ve numaranın engellenmesine yol açabilir. Bu yüzden uygulama “hazırla, siz gönderin” yöntemini kullanır; çok kişiye yalnızca iletişimi kabul etmiş kişilere (ör. personel) yazın.

## Güncelleme sistemi

**Kullanıcı tarafı:** Yardım ▸ *Güncellemeleri denetle* (ve açılışta günde bir kez otomatik). Yeni sürüm varsa notlarıyla birlikte sorar; `.exe` sürümünde **Evet** derseniz indirir, doğrular, programı kapatıp yenisiyle açar. Kaynak koddan çalışıyorsanız sürüm sayfasını açar. Veriler `%APPDATA%` altında durduğu için güncellemeden etkilenmez.

**Yayıncı tarafı (sizin yapacağınız):**
1. `version.py` içindeki `UPDATE_REPO` değerini kendi deponuza ayarlayın (`kullaniciadi/isletme-paneli`, depo **public** olmalı) — bir kez.
2. Değişikliği yapın, `version.py` içindeki `VERSION`'ı artırın (ör. `1.2.0` → `1.3.0`).
3. ```
   git add . && git commit -m "v1.3.0: ..."
   git tag v1.3.0
   git push && git push origin v1.3.0
   ```
4. GitHub Actions testleri çalıştırıp `.exe` + `.sha256` dosyalarını **Releases** sayfasında yayınlar. Sürüm açıklaması (release notes) kullanıcıya güncelleme penceresinde gösterilir.

Güvenlik notu: indirme yalnızca `https://github.com/` adresinden yapılır ve SHA256 ile doğrulanır. Dosya kod imzalı değildir; GitHub hesabınızı iki adımlı doğrulamayla koruyun.

## Kullanım ipuçları

- `Ctrl+F` arama kutusuna gider, `Ctrl+N` yeni kayıt, `Esc` aramayı temizler, `Delete` seçili kaydı siler.
- Sütun başlığına tıklayarak sıralayın. Satıra çift tıklayarak düzenleyin.
- Düzen ▸ **Kategorileri ve alanları yönet** ile yapıyı istediğiniz zaman değiştirin; mevcut kayıtlar korunur.
- Hızlı ekleme: `+ Kategori | değer | değer`. `Alan=Değer` biçimiyle belirli alanı da seçebilirsiniz:
  `+ Müşteri | Firma / Ad=Yıldız Ltd | Telefon=0212 555 11 22`

## Yapay zekâ (ücretsiz)

1. **Dahili akıllı arama** (her zaman açık, internetsiz): doğal cümleleri (“Ahmet'in telefon numarası”) anlar, ek ve noktalamayı ayıklar, ilgili alanı bulup doğrudan yanıtlar. Bu bir sohbet modeli değil, hafif kural tabanlı bir yardımcıdır.
2. **İsteğe bağlı gerçek yapay zekâ — [Ollama](https://ollama.com)** (açık kaynak, ücretsiz, yerel): kurup `ollama pull llama3.2` çalıştırın, sonra Ayarlar ▸ *Ollama'yı kullan*'ı işaretleyin. Serbest sorular (“kaç personelim var?”) sorabilirsiniz. Her şey bilgisayarınızda çalışır; **gizli alanlar modele gönderilmez**. Modellerin kendi lisansları vardır (ör. Llama, Gemma, Qwen) — kullanmadan önce kontrol edin. Küçük modeller hata yapabilir; kritik bilgileri kayıttan doğrulayın.

## Veri ve gizlilik (önemli)

- Veri dosyası: `%APPDATA%\IsletmePaneli\isletme.db`, yedekler aynı klasörde `yedekler\`. (Ayarlar'da yol görünür; Dosya ▸ *Veri klasörünü aç*.)
- **Taşınabilir mod:** `IsletmePaneli.exe`'nin yanına `veri` adlı boş bir klasör açarsanız tüm veriler orada tutulur (USB bellek için ideal).
- Veritabanı **şifrelenmez**. TC kimlik no gibi kişisel veriler KVKK kapsamındadır; bilgisayarınızda **BitLocker** (disk şifreleme) ve Windows hesap parolası kullanmanızı, yedekleri güvenli yerde saklamanızı öneririz. “Gizli alan” özelliği yalnızca ekrandan göz atmaya karşı bir kolaylıktır, şifreleme değildir.
- Geri yükleme: uygulamayı kapatın, yedek `.db` dosyasını `isletme.db` adıyla veri klasörüne kopyalayın.

## Geliştirme

```
app.py              Arayüz (Tkinter)
webinbox.py         Web formu başvurularını çeken istemci
web/                PHP sitesi (form, api.php, KURULUM.md)
whatsapp.py         Numara düzeltme, mesaj şablonu, WhatsApp bağlantısı
updater.py          GitHub Releases ile güncelleme
version.py          Sürüm numarası ve güncelleme deposu
listsync.py         Excel/CSV okuma ve telefonla karşılaştırma
core.py             Veritabanı, arama, akıllı yanıt, içe/dışa aktarma, Ollama
tests/test_core.py  Birim testleri   ->  python -m unittest discover -s tests
build.bat           .exe üretir (PyInstaller)
.github/workflows   GitHub'da otomatik .exe derleme
```

Katkılar (Pull Request) memnuniyetle karşılanır. Fikirler: uygulama parolası/şifreli veritabanı, tarih alanı türü ve hatırlatma (ör. ehliyet/sigorta bitişi), dosya/belge ekleme, çoklu kullanıcı.

## English (short)

**İşletme Paneli** ("Business Panel") is an offline Windows desktop app that keeps all your business records (staff, customers, suppliers…) in a local SQLite file and finds anything from a single search box. Fully customizable categories and fields, sensitive-field masking, Turkish-aware fuzzy search, a built-in rule-based "smart ask", optional local LLM via Ollama, backups and JSON/CSV export. Pure Python standard library (Tkinter). MIT licensed. Run `python app.py` or build an `.exe` with `build.bat`.
