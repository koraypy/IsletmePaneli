<?php
// Bu dosyayı "config.php" adıyla kopyalayıp düzenleyin. (config.php'yi kimseyle paylaşmayın.)
// İpucu: panelde Ayarlar ▸ Web formu ▸ "Anahtar üret" size aşağıdaki iki satırı hazır verir.
return [
    'site_title'  => 'Personel Bilgi Formu',
    'company'     => 'Şirket Adı',

    // Personele verdiğiniz davet kodu (formu yalnızca kodu bilenler doldurabilir).
    'access_code' => 'DEGISTIR',

    // Panelin başvuruları çekerken kullandığı gizli anahtar (en az 20 karakter, rastgele).
    // Panel > Ayarlar'daki anahtarla AYNI olmalı.
    'api_key'     => 'DEGISTIR_UZUN_RASTGELE_BIR_ANAHTAR',

    // Başvuruların geçici saklandığı klasör. Mümkünse web kök dizininin DIŞINDA bir yol verin.
    'data_dir'    => __DIR__ . '/data',

    'max_per_hour'     => 15,   // bir IP'nin saatte yapabileceği deneme sayısı
    'max_pending'      => 300,  // sunucuda bekleyebilecek en çok başvuru
    'min_fill_seconds' => 3,    // bot koruması: formu bundan hızlı gönderenler reddedilir
    // Site bir vekil/proxy arkasındaysa ve herkes aynı IP görünüyorsa, gerçek IP başlığını yazın:
    // 'ip_header' => 'HTTP_CF_CONNECTING_IP',
    'ip_header'   => '',

    // ÖNEMLİ: "name" değerleri panelde kategorinizdeki alan adlarıyla AYNI yazılmalıdır.
    // type: text | long | phone | email | tckn
    'fields' => [
        ['name' => 'Ad Soyad',  'type' => 'text',  'required' => true, 'max' => 80, 'autocomplete' => 'name'],
        ['name' => 'Telefon',   'type' => 'phone', 'required' => true, 'autocomplete' => 'tel'],
        ['name' => 'E-posta',   'type' => 'email', 'max' => 120, 'autocomplete' => 'email'],
        ['name' => 'Görev',     'type' => 'text',  'max' => 60],
        ['name' => 'Notlar',    'type' => 'long',  'max' => 500],
        // TC kimlik numarasını internetten toplamanız ÖNERİLMEZ (KVKK riski). Gerekirse açın:
        // ['name' => 'TC Kimlik No', 'type' => 'tckn', 'required' => true, 'max' => 11,
        //  'help' => 'Yalnızca 11 haneli numaranızı yazın.'],
    ],

    'kvkk_text' => 'Verdiğim bilgilerin, işletme tarafından personel kaydı ve iletişim amacıyla '
                 . 'işlenmesini kabul ediyorum. Bilgiler panele aktarıldıktan sonra bu sunucudan silinir.',
    'success_text' => 'Teşekkürler! Bilgileriniz alındı.',
];
