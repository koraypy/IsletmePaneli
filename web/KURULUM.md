# Web formu kurulumu (PHP)

Personel, telefonundan bir bağlantıya girip bilgilerini kendisi doldurur. Başvurular sunucuda **geçici** durur; panel onları çeker, kontrol edersiniz, onaylayınca panele eklenir ve sunucudan **silinir**.

```
Personel (telefon) ──► web/index.php ──► sunucuda geçici JSON ──► Panel (web/api.php ile çeker) ──► kayıt + sunucudan silme
```

## 1) Ücretsiz hosting ve adres
- PHP 8 çalıştıran, ücretsiz **HTTPS (SSL)** veren bir hosta kayıt olun (ör. InfinityFree). “Ücretsiz domain” genelde hostun verdiği alt alan adıdır (`adiniz.hostadi.com` gibi); kendi `.com` adresiniz ücretlidir.
- Tahmin edilmesi zor bir alt alan adı seçin. Site arama motorlarına zaten kapalıdır (`noindex`).
- **Adresin `https://` ile açıldığından emin olun.** Panel, `https` olmayan adrese bağlanmaz.

## 2) Dosyaları yükleme
Bu klasördeki (`web/`) dosyaların **içeriğini** hostun web klasörüne (genelde `htdocs`) yükleyin (hostun Dosya Yöneticisi ya da FTP ile):
`index.php`, `api.php`, `lib.php`, `style.css`, `.htaccess`, `config.sample.php`

> `.htaccess` gizli dosyadır; yüklendiğinden emin olun (dosya yöneticisinde “gizli dosyaları göster”).

## 3) Yapılandırma (`config.php`)
1. Panelde **Düzen ▸ Ayarlar ▸ Web formu ▸ Anahtar üret**'e basın. Davet kodu ve API anahtarı üretilir, şu iki satır **panoya kopyalanır**:
   ```php
   'access_code' => 'ABCD-2345',
   'api_key'     => '....uzun rastgele....',
   ```
2. Hostta `config.sample.php` dosyasını **`config.php`** olarak kopyalayın ve düzenleyin: `access_code` ve `api_key` satırlarını panodakilerle değiştirin, `company` ve `site_title` alanlarını yazın.
3. Panelde Ayarlar'a **site adresini** (ör. `https://adiniz.hostadi.com/`) yazıp **Kaydet**'e basın.
4. **Bağlantıyı dene** → “Bağlandı” görmelisiniz.

### Form alanları
`config.php` içindeki `fields` listesi formu belirler. **Alan adları (`name`) panelde kategorinizdeki alan adlarıyla aynı yazılmalıdır** (büyük/küçük harf ve Türkçe karakter fark etmez); eşleşmeyen alanlar panele aktarılmaz ve başvuru ekranında uyarı olarak görünür. Telefon alanı zorunlu kalmalı, kişiler telefonla tanınır.

## 4) Test
1. Adresi telefondan açın, davet kodunu ve bilgileri girip gönderin.
2. Panel ▸ **Dosya ▸ Web başvuruları** → başvuru “Yeni” olarak görünür. **Seçilileri işle** deyin: kayıt panele eklenir, sunucudan silinir.
3. Aynı kişiyi (aynı telefon) tekrar gönderirseniz “Zaten kayıtlı” ya da “Bilgisi farklı” görünür; yeni kayıt açılmaz.

## 5) Personele davet
Panelde kişiyi seçin ▸ **💬 WhatsApp** ▸ şablon **“Bilgi formu”**: `{form_linki}` ve `{davet_kodu}` Ayarlar'dakilerle dolar.

## Güvenlik ve KVKK — lütfen okuyun
- **TC kimlik numarasını web formundan toplamayın.** Varsayılan formda yoktur. Ücretsiz hostlarda veri güvenliği ve erişim kayıtları üzerinde denetiminiz sınırlıdır.
- Form sayfasına bir **aydınlatma metni** koyun (`kvkk_text`); metni kendi KVKK sürecinize göre düzenleyin. Bu yazılım hukuki danışmanlık değildir.
- Başvurular yalnızca sunucuda **geçici** durur; panel onaylayınca silinir. Sunucuda IP adresi saklanmaz (hız sınırı için yalnızca geri döndürülemez özet tutulur).
- Davet kodunu zaman zaman değiştirin (`config.php`'de ve panelde); kod sızarsa yabancılar başvuru gönderebilir. Her başvuru zaten panelde sizin onayınızdan geçer.
- Korumalar: davet kodu, saatlik IP sınırı, gizli bot tuzağı, zaman damgalı imzalı form belirteci, en fazla 300 bekleyen başvuru, API için anahtar + hatalı deneme kilidi, sıkı CSP başlıkları, tüm çıktılar kaçışlı.
- `data/` klasörü `.htaccess` ile dışarıya kapatılır. Host Apache değilse (ör. nginx) `.htaccess` çalışmaz; bu durumda `config.php` içindeki `data_dir`'i web kökünün **dışındaki** bir klasöre yönlendirin.
- Ücretsiz hostlar bazen tarayıcı olmayan isteklere bot doğrulaması koyar; panel bu durumda “beklenen JSON yerine başka yanıt” der. “Bağlantıyı dene”yi kurulumun en başında yapın; çözülmezse hosta destek açın ya da başka bir host deneyin.
- Hostun sunucusu çökerse ya da hesabı kapatılırsa henüz çekilmemiş başvurular kaybolabilir; başvuruları düzenli çekin (panel her 15 dakikada bir bekleyen sayısını kontrol eder).
