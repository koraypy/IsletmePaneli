<?php
declare(strict_types=1);
require __DIR__ . '/lib.php';
security_headers();

$c = cfg();
$fields = is_array($c['fields'] ?? null) ? $c['fields'] : [];
$ready = !is_placeholder((string)($c['access_code'] ?? ''))
    && strlen((string)($c['api_key'] ?? '')) >= 20
    && !is_placeholder((string)($c['api_key'] ?? ''));

$errors = [];
$done = false;
$old = [];

if ($ready && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $values = [];
    foreach ($fields as $i => $f) {
        $raw = $_POST['f' . $i] ?? '';
        $v = is_string($raw) ? clean($raw, ($f['type'] ?? 'text') === 'long') : '';
        $old[$i] = $v;
        $values[(string)$f['name']] = $v;
    }

    $ip = client_ip();
    if (rl_count('form', $ip) >= (int)($c['max_per_hour'] ?? 15)) {
        http_response_code(429);
        $errors[] = 'Çok fazla deneme yapıldı. Lütfen bir süre sonra tekrar deneyin.';
    } else {
        rl_add('form', $ip);
        if (!empty($_POST['website'])) {
            $done = true; // bot tuzağı: sessizce başarılı göster, kaydetme
        } elseif (!check_token((string)($_POST['tok'] ?? ''), (int)($c['min_fill_seconds'] ?? 3))) {
            $errors[] = 'Form süresi dolmuş ya da çok hızlı gönderilmiş. Lütfen tekrar deneyin.';
        } elseif (!hash_equals((string)$c['access_code'], trim((string)($_POST['code'] ?? '')))) {
            usleep(700000);
            $errors[] = 'Davet kodu hatalı.';
        } elseif (empty($_POST['kvkk'])) {
            $errors[] = 'Devam etmek için aydınlatma metnini onaylamanız gerekir.';
        } else {
            foreach ($fields as $i => $f) {
                $err = check_field($f, $values[(string)$f['name']]);
                if ($err !== null) {
                    $errors[] = $err;
                }
            }
            if (!$errors) {
                $dir = data_dir('pending');
                $existing = glob($dir . '/*.json');
                if (is_array($existing) && count($existing) >= (int)($c['max_pending'] ?? 300)) {
                    $errors[] = 'Şu anda yeni başvuru alınamıyor. Lütfen yöneticiyle iletişime geçin.';
                } else {
                    $id = bin2hex(random_bytes(16));
                    $payload = json_encode(
                        ['id' => $id, 'received' => gmdate('c'), 'fields' => $values],
                        JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES
                    );
                    $tmp = $dir . '/.' . $id . '.tmp';
                    if ($payload === false
                        || file_put_contents($tmp, $payload, LOCK_EX) === false
                        || !rename($tmp, $dir . '/' . $id . '.json')) {
                        $errors[] = 'Kaydedilemedi. Lütfen daha sonra tekrar deneyin.';
                    } else {
                        $done = true;
                        $old = [];
                    }
                }
            }
        }
    }
}
?>
<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title><?= h((string)($c['site_title'] ?? 'Form')) ?></title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<main class="card">
  <p class="brand"><?= h((string)($c['company'] ?? '')) ?></p>
  <h1><?= h((string)($c['site_title'] ?? 'Form')) ?></h1>

<?php if (!$ready): ?>
  <p class="msg err">Site kurulumu tamamlanmamış. (config.php içinde access_code ve api_key ayarlanmalı.)</p>
<?php elseif ($done): ?>
  <p class="msg ok"><?= h((string)($c['success_text'] ?? 'Teşekkürler!')) ?></p>
<?php else: ?>
  <?php foreach ($errors as $e): ?>
    <p class="msg err"><?= h($e) ?></p>
  <?php endforeach; ?>

  <form method="post" action="index.php" autocomplete="on">
    <input type="hidden" name="tok" value="<?= h(form_token()) ?>">
    <div class="hp" aria-hidden="true">
      <label for="website">Bu alanı boş bırakın</label>
      <input id="website" name="website" type="text" tabindex="-1" autocomplete="off">
    </div>

    <label for="code">Davet kodu *</label>
    <input id="code" name="code" type="text" required autocomplete="off" autocapitalize="characters">

<?php foreach ($fields as $i => $f):
    $type = (string)($f['type'] ?? 'text');
    $id = 'f' . $i;
    $val = (string)($old[$i] ?? '');
    $max = (int)($f['max'] ?? 120);
    $req = !empty($f['required']) ? ' required' : '';
    $ac = h((string)($f['autocomplete'] ?? 'off'));
?>
    <label for="<?= $id ?>"><?= h((string)$f['name']) ?><?= $req !== '' ? ' *' : '' ?></label>
<?php if (!empty($f['help'])): ?>
    <small><?= h((string)$f['help']) ?></small>
<?php endif; ?>
<?php if ($type === 'long'): ?>
    <textarea id="<?= $id ?>" name="<?= $id ?>" rows="4" maxlength="<?= $max ?>"<?= $req ?>><?= h($val) ?></textarea>
<?php else:
    $it = $type === 'phone' ? 'tel' : ($type === 'email' ? 'email' : 'text');
    $mode = $type === 'tckn' ? ' inputmode="numeric" pattern="[0-9]{11}"' : '';
?>
    <input id="<?= $id ?>" name="<?= $id ?>" type="<?= $it ?>" maxlength="<?= $max ?>" value="<?= h($val) ?>" autocomplete="<?= $ac ?>"<?= $mode ?><?= $req ?>>
<?php endif; ?>
<?php endforeach; ?>

    <label class="check">
      <input type="checkbox" name="kvkk" value="1" required>
      <span><?= h((string)($c['kvkk_text'] ?? '')) ?></span>
    </label>

    <button type="submit">Gönder</button>
  </form>
<?php endif; ?>
</main>
</body>
</html>
