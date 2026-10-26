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
listsync.py         Excel/CSV okuma ve telefonla karşılaştırma
core.py             Veritabanı, arama, akıllı yanıt, içe/dışa aktarma, Ollama
tests/test_core.py  Birim testleri   ->  python -m unittest discover -s tests
build.bat           .exe üretir (PyInstaller)
.github/workflows   GitHub'da otomatik .exe derleme
```

Katkılar (Pull Request) memnuniyetle karşılanır. Fikirler: uygulama parolası/şifreli veritabanı, tarih alanı türü ve hatırlatma (ör. ehliyet/sigorta bitişi), dosya/belge ekleme, çoklu kullanıcı.

## English (short)

**İşletme Paneli** ("Business Panel") is an offline Windows desktop app that keeps all your business records (staff, customers, suppliers…) in a local SQLite file and finds anything from a single search box. Fully customizable categories and fields, sensitive-field masking, Turkish-aware fuzzy search, a built-in rule-based "smart ask", optional local LLM via Ollama, backups and JSON/CSV export. Pure Python standard library (Tkinter). MIT licensed. Run `python app.py` or build an `.exe` with `build.bat`.
