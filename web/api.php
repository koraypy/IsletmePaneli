<?php
declare(strict_types=1);
require __DIR__ . '/lib.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
header('X-Robots-Tag: noindex, nofollow');

function out(array $data, int $code = 200): void
{
    http_response_code($code);
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

$c = cfg();
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    out(['ok' => false, 'error' => 'Yalnızca POST kabul edilir.'], 405);
}
$apiKey = (string)($c['api_key'] ?? '');
if (strlen($apiKey) < 20 || is_placeholder($apiKey)) {
    out(['ok' => false, 'error' => 'Sunucuda api_key ayarlanmamış (config.php).'], 500);
}

$ip = client_ip();
if (rl_count('apifail', $ip) >= 10) {
    out(['ok' => false, 'error' => 'Çok fazla hatalı deneme. Bir saat sonra tekrar deneyin.'], 429);
}

$body = (string)file_get_contents('php://input', false, null, 0, 200000);
$in = json_decode($body, true);
if (!is_array($in)) {
    out(['ok' => false, 'error' => 'Geçersiz istek.'], 400);
}
if (!hash_equals($apiKey, (string)($in['key'] ?? ''))) {
    rl_add('apifail', $ip);
    usleep(700000);
    out(['ok' => false, 'error' => 'Anahtar hatalı.'], 401);
}

$dir = data_dir('pending');
$files = glob($dir . '/*.json');
$files = is_array($files) ? $files : [];
$action = (string)($in['action'] ?? '');

if ($action === 'ping') {
    $names = [];
    foreach ((is_array($c['fields'] ?? null) ? $c['fields'] : []) as $f) {
        $names[] = (string)$f['name'];
    }
    out(['ok' => true, 'pending' => count($files), 'fields' => $names]);
}

if ($action === 'list') {
    usort($files, function ($a, $b) {
        return (filemtime($a) ?: 0) <=> (filemtime($b) ?: 0);
    });
    $items = [];
    foreach (array_slice($files, 0, 200) as $f) {
        $d = json_decode((string)@file_get_contents($f), true);
        if (is_array($d) && isset($d['id'], $d['fields']) && is_array($d['fields'])) {
            $items[] = $d;
        }
    }
    out(['ok' => true, 'items' => $items, 'pending' => count($files)]);
}

if ($action === 'ack') {
    $ids = is_array($in['ids'] ?? null) ? $in['ids'] : [];
    $deleted = 0;
    foreach ($ids as $id) {
        if (is_string($id) && preg_match('/^[a-f0-9]{32}$/', $id) === 1) {
            $path = $dir . '/' . $id . '.json';
            if (is_file($path) && @unlink($path)) {
                $deleted++;
            }
        }
    }
    out(['ok' => true, 'deleted' => $deleted]);
}

out(['ok' => false, 'error' => 'Bilinmeyen işlem.'], 400);
