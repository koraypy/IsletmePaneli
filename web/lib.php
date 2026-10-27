<?php
declare(strict_types=1);

function cfg(): array
{
    static $c = null;
    if ($c === null) {
        $file = __DIR__ . '/config.php';
        if (!is_file($file)) {
            http_response_code(500);
            exit('config.php bulunamadi. config.sample.php dosyasini config.php adiyla kopyalayip duzenleyin.');
        }
        $c = require $file;
    }
    return $c;
}

function h(string $s): string
{
    return htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function slen(string $s): int
{
    return function_exists('mb_strlen') ? mb_strlen($s, 'UTF-8') : strlen($s);
}

function is_placeholder(string $v): bool
{
    return $v === '' || strpos($v, 'DEGISTIR') === 0;
}

function data_dir(string $sub = ''): string
{
    $base = rtrim((string)(cfg()['data_dir'] ?? (__DIR__ . '/data')), '/\\');
    $dir = $sub === '' ? $base : $base . '/' . $sub;
    if (!is_dir($dir)) {
        @mkdir($dir, 0755, true);
    }
    $guard = $base . '/.htaccess';
    if (!is_file($guard)) {
        @file_put_contents($guard, "<IfModule mod_authz_core.c>\nRequire all denied\n</IfModule>\n"
            . "<IfModule !mod_authz_core.c>\nDeny from all\n</IfModule>\n");
    }
    if (!is_file($base . '/index.html')) {
        @file_put_contents($base . '/index.html', '');
    }
    return $dir;
}

function security_headers(): void
{
    header("Content-Security-Policy: default-src 'none'; style-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: DENY');
    header('Referrer-Policy: no-referrer');
    header('X-Robots-Tag: noindex, nofollow');
    header('Cache-Control: no-store');
}

function client_ip(): string
{
    $hdr = (string)(cfg()['ip_header'] ?? '');
    if ($hdr !== '' && !empty($_SERVER[$hdr])) {
        $ip = trim(explode(',', (string)$_SERVER[$hdr])[0]);
        if (filter_var($ip, FILTER_VALIDATE_IP)) {
            return $ip;
        }
    }
    return (string)($_SERVER['REMOTE_ADDR'] ?? '0.0.0.0');
}

// ---- Basit hız sınırlama (IP başına, saatlik; IP yalnızca sha1 özetiyle saklanır) ----
function rl_file(string $bucket, string $ip): string
{
    return data_dir('rate') . '/' . $bucket . '_' . sha1($ip) . '.json';
}

function rl_load(string $bucket, string $ip): array
{
    $f = rl_file($bucket, $ip);
    $a = is_file($f) ? json_decode((string)@file_get_contents($f), true) : [];
    $limit = time() - 3600;
    return array_values(array_filter(is_array($a) ? $a : [], function ($t) use ($limit) {
        return is_int($t) && $t > $limit;
    }));
}

function rl_count(string $bucket, string $ip): int
{
    return count(rl_load($bucket, $ip));
}

function rl_add(string $bucket, string $ip): void
{
    $a = rl_load($bucket, $ip);
    $a[] = time();
    @file_put_contents(rl_file($bucket, $ip), json_encode($a), LOCK_EX);
}

// ---- Oturumsuz CSRF / bot belirteci (zaman damgası + HMAC) ----
function form_token(): string
{
    $t = time();
    return $t . '.' . hash_hmac('sha256', 'form|' . $t, (string)cfg()['api_key']);
}

function check_token(string $tok, int $minAge): bool
{
    $p = explode('.', $tok, 2);
    if (count($p) !== 2 || !ctype_digit($p[0])) {
        return false;
    }
    $t = (int)$p[0];
    if (!hash_equals(hash_hmac('sha256', 'form|' . $t, (string)cfg()['api_key']), $p[1])) {
        return false;
    }
    $age = time() - $t;
    return $age >= $minAge && $age <= 7200;
}

// ---- Doğrulama ----
function clean(string $v, bool $multiline): string
{
    if (preg_match('//u', $v) !== 1) {
        return '';
    }
    $v = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/', '', trim($v)) ?? '';
    if (!$multiline) {
        $v = preg_replace('/\s+/u', ' ', $v) ?? '';
    }
    return $v;
}

function valid_tckn(string $v): bool
{
    if (preg_match('/^[1-9][0-9]{10}$/', $v) !== 1) {
        return false;
    }
    $d = array_map('intval', str_split($v));
    $odd = $d[0] + $d[2] + $d[4] + $d[6] + $d[8];
    $even = $d[1] + $d[3] + $d[5] + $d[7];
    if ((($odd * 7 - $even) % 10 + 10) % 10 !== $d[9]) {
        return false;
    }
    return array_sum(array_slice($d, 0, 10)) % 10 === $d[10];
}

function check_field(array $f, string $v): ?string
{
    $label = (string)$f['name'];
    if ($v === '') {
        return !empty($f['required']) ? "“{$label}” alanı zorunludur." : null;
    }
    $max = (int)($f['max'] ?? 120);
    if (slen($v) > $max) {
        return "“{$label}” en fazla {$max} karakter olabilir.";
    }
    switch ($f['type'] ?? 'text') {
        case 'phone':
            $digits = preg_replace('/\D/', '', $v) ?? '';
            if (preg_match('/^[0-9+\s().\/-]+$/', $v) !== 1 || strlen($digits) < 10 || strlen($digits) > 15) {
                return "“{$label}” geçerli bir telefon numarası olmalıdır.";
            }
            break;
        case 'email':
            if (!filter_var($v, FILTER_VALIDATE_EMAIL)) {
                return "“{$label}” geçerli bir e-posta adresi olmalıdır.";
            }
            break;
        case 'tckn':
            if (!valid_tckn($v)) {
                return "“{$label}” geçerli bir T.C. kimlik numarası olmalıdır.";
            }
            break;
    }
    return null;
}
