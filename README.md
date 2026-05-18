# Odoo Yardım Asistanı

Odoo 19 Community içinde çalışan, **yerel** yapay zekâ destekli Türkçe bir sohbet
asistanı. Kullanıcı Odoo ekranından çıkmadan doğal dille soru sorar; asistan da
ona resmi Odoo dokümantasyonundan beslenen, adım adım Türkçe cevaplar verir.

- Modül adı: `odoo_help_assistant`
- Sürüm: `19.0.1.2.0`
- Lisans: LGPL-3
- LLM: Ollama (yerel — internet erişimi gerekmez)
- Repo: <https://github.com/rasimokutan/Odoo-Yardim-Asistani>

> Bu modül kod üreten bir araç **değildir**. Amacı son kullanıcıya Odoo
> içindeki menü yolları, ekran adımları ve operasyonel sorular konusunda
> rehberlik etmektir.

---

## İçindekiler

1. [Ne işe yarıyor?](#ne-işe-yarıyor)
2. [Mimari](#mimari)
3. [Kurulum](#kurulum)
4. [RAG (Doküman Tabanlı Cevap)](#rag-doküman-tabanlı-cevap)
5. [Ayarlar](#ayarlar)
6. [Kullanım](#kullanım)
7. [Güvenlik & Yetkiler](#güvenlik--yetkiler)
8. [Sorun Giderme](#sorun-giderme)
9. [Geliştirici Notları](#geliştirici-notları)

---

## Ne işe yarıyor?

Kullanıcı Odoo içinde bir sohbet ekranı açar ve şu tip soruları sorabilir:

- "Satış teklifini nasıl onaylarım?"
- "Stok transferinde Doğrula butonu neden görünmüyor?"
- "Faturayı ödeme ile nasıl eşleştiririm?"
- "CRM fırsatında aktiviteyi nereden eklerim?"
- "Satın alma siparişini hangi menüden bulurum?"

Cevaplar varsayılan olarak **Türkçe** olarak gelir. Kullanıcı açıkça farklı bir
dil isterse o dilde de yanıtlanabilir.

### Öne çıkan özellikler

- Odoo içinden çalışan, Owl tabanlı sohbet ekranı
- Niyet (intent) sınıflandırıcı: selamlama / Odoo sorusu / belirsiz
- **RAG**: Resmi `odoo/documentation` reposundan indekslenmiş chunk'lardan
  ilgili pasajları çekip yanıta enjekte eder
- Yerel Ollama LLM — internet bağımlılığı yok
- Konuşma geçmişi DB'de saklanır, kullanıcı/şirket izolasyonu uygulanır
- Yönetici için tüm sohbetleri ve indeks durumunu görme ekranları
- Türkçe ipucu (hint) katmanı: satış, stok, muhasebe, CRM gibi alanlar için
  hazır kısa kılavuzlar

---

## Mimari

```
Kullanıcı sorusu
  → intent_detector       (greeting / odoo_question / unclear)
  → prompt_templates      (intent'e göre sistem prompt seç)
  → rag_retriever         (en alakalı 3 chunk'ı cosine similarity ile getir)
  → chatbot_service       (prompt + history + RAG bağlamı + ipuçları)
  → ollama_provider       (Ollama /api/chat)
  → LLM yanıtı → DB'ye kaydet → frontend'e döndür
```

### Veritabanı modelleri

| Tablo                   | Amaç                                              |
| ----------------------- | ------------------------------------------------- |
| `odoo_chatbot_session`  | Sohbet oturumu                                    |
| `odoo_chatbot_message`  | Bireysel mesaj (role: user / assistant / system)  |
| `odoo_rag_chunk`        | RST chunk + 768-dim embedding (JSON)              |
| `odoo_rag_index_wizard` | Transient — indeksleme sihirbazı                  |

### Dosya yapısı

```
odoo_help_assistant/
├── __manifest__.py
├── controllers/main.py                 JSON-RPC endpoint'leri
├── models/
│   ├── chatbot_session.py              Oturum modeli + send_chat_message()
│   ├── chatbot_message.py              Mesaj modeli
│   ├── rag_chunk.py                    RAG chunk + embedding
│   └── res_config_settings.py          Ayarlar
├── services/
│   ├── chatbot_service.py              Prompt inşası, RAG, LLM çağrısı
│   ├── intent_detector.py              Niyet sınıflandırıcı
│   ├── prompt_templates.py             Niyet başına sistem prompt
│   ├── ollama_provider.py              Ollama /api/chat istemcisi
│   ├── embedding_service.py            Ollama /api/embed istemcisi
│   ├── rag_retriever.py                Cosine similarity arama
│   ├── doc_indexer.py                  git clone → chunk → embed → DB
│   └── odoo_hints.py                   Statik Türkçe ipuçları
├── wizards/index_docs_wizard.py        İndeksleme UI
├── scripts/index_docs_cli.py           Standalone CLI indekser
├── views/                              XML görünüm + menüler
├── static/src/                         Owl arayüz + SCSS
├── security/                           Gruplar + record rule
└── tests/test_chatbot.py
```

---

## Kurulum

### Ön koşullar

- Odoo 19 Community
- PostgreSQL (Odoo'nun bağlı olduğu)
- [Ollama](https://ollama.com/) yüklü ve servis çalışıyor olmalı
- Sistem PATH'inde `git` bulunmalı (indeksleme için repo klonu)
- (Opsiyonel) `numpy` — cosine similarity'i hızlandırır

### 1. Ollama modellerini indir

```bash
ollama pull llama3.2:3b           # Türkçe için: hafif ve hızlı
ollama pull nomic-embed-text      # RAG embedding modeli (zorunlu)
```

Daha kaliteli Türkçe cevap için (~7B sınıfı):

```bash
ollama pull qwen2.5:7b
```

### 2. Modülü addons path'e koy

```
custom_addons/odoo_help_assistant
```

`odoo.conf` içinde `addons_path` bu klasörü kapsamalıdır.

### 3. Modülü yükle

Odoo'yu başlatın → Uygulamalar → Uygulama listesini güncelle →
"Odoo Yardım Asistanı"nı yükle.

CLI ile:

```powershell
venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo19_v1 ^
    -i odoo_help_assistant --stop-after-init
```

### 4. Sohbet ekranını aç

Sol menüden **Yardım Asistanı** uygulamasına girin ve sohbete başlayın.

---

## RAG (Doküman Tabanlı Cevap)

Asistan, resmi
[odoo/documentation](https://github.com/odoo/documentation) reposundan
indekslenmiş Odoo dokümantasyonunu kullanır.

### Nasıl çalışır?

1. Repo lokal cache'e `git clone --depth=1 --branch 19.0` ile çekilir.
2. `content/applications/` altındaki seçili alt klasörler taranır.
3. Her `.rst` dosyası ~350 kelimelik, 50 kelime örtüşmeli chunk'lara bölünür.
4. Her chunk `nomic-embed-text` ile 768-boyutlu vektöre çevrilir.
5. Vektörler `odoo_rag_chunk` tablosuna JSON olarak yazılır.
6. Soru geldiğinde aynı modelle embed edilir, cosine similarity ile en
   alakalı 3 chunk seçilir ve sistem prompt'una eklenir.

> **Neden API değil, `git clone`?** GitHub REST API anonim kullanımda
> saatte 60 istek ile sınırlıdır. Eski indeksleyici her alt klasör için ayrı
> API çağrısı yapıyor, limit aşıldığında sessizce boş liste döndürüyor ve
> sonuç "0/0/0 chunk" oluyordu. Yeni indeksleyici doğrudan `git` üzerinden
> çalışır, rate-limit problemi yoktur.

### A) Web wizard ile indeksleme

1. Yardım Asistanı → **Dokümantasyonu İndeksle**
2. Branch: `19.0`
3. Maksimum dosya: 150 (varsayılan) → 5-8 dakika
4. **İndekslemeyi Başlat** butonuna bas

> Tarayıcı çok uzun süren istekleri zaman aşımına uğratırsa B yöntemini
> kullanın.

### B) Standalone CLI ile indeksleme

Odoo çalışırken bile, terminalden:

```powershell
venv\Scripts\python.exe ^
    custom_addons\odoo_help_assistant\scripts\index_docs_cli.py ^
    --db odoo19_v1 --branch 19.0 --max-files 220
```

Faydalı parametreler:

| Parametre        | Açıklama                                            |
| ---------------- | --------------------------------------------------- |
| `--db`           | Hedef PostgreSQL veritabanı (varsayılan `odoo19_v1`) |
| `--branch`       | Doküman branch'i (`19.0`, `18.0`, `17.0`)           |
| `--max-files`    | Toplam dosya tavanı (varsayılan 80)                 |
| `--per-section`  | Section başına dosya tavanı (yoksa eşit dağıtılır)  |
| `--no-clear`     | Mevcut chunk'ları silmeden ekle                     |
| `--dirs`         | Sadece belirli alt klasörleri tara                  |

Ortam değişkenleri: `OLLAMA_URL`, `EMBED_MODEL`, `PGHOST`, `PGPORT`,
`PGUSER`, `PGPASSWORD`.

### İndeks durumunu kontrol et

Yardım Asistanı → **İndeks Durumu** ekranı tüm chunk'ları listeler
(title, section, kaynak URL).

### Dengeli dağıtım

Indekser tek bir büyük klasörün (örn. `inventory_and_mrp`) tüm kotayı
yutmaması için round-robin uygular: `max_files` mevcut section sayısına
bölünür ve dosyalar sırayla section'lardan toplanır.

---

## Ayarlar

`Ayarlar → Yardım Asistanı` ekranından veya `ir.config_parameter` ile
yönetilir.

| Anahtar                                       | Varsayılan                  |
| --------------------------------------------- | --------------------------- |
| `odoo_help_assistant.chatbot_enabled`         | `True`                      |
| `odoo_help_assistant.chatbot_provider`        | `ollama`                    |
| `odoo_help_assistant.ollama_base_url`         | `http://127.0.0.1:11434`    |
| `odoo_help_assistant.model_name`              | `llama3.2:3b`               |
| `odoo_help_assistant.temperature`             | `0.2`                       |
| `odoo_help_assistant.max_tokens`              | `300`                       |
| `odoo_help_assistant.timeout`                 | `120`                       |
| `odoo_help_assistant.include_user_context`    | `True`                      |
| `odoo_help_assistant.hint_layer_enabled`      | `True`                      |
| `odoo_help_assistant.system_prompt`           | (varsayılan TR prompt)      |

---

## Kullanım

1. Sol menüden **Yardım Asistanı**'na git
2. **+ Yeni Sohbet** ile oturum aç
3. Sorunu Türkçe yaz → asistan yanıt verir
4. Geçmiş otomatik kaydedilir, son ~5 alışveriş prompt'a dahil edilir

### Niyet (intent) tipleri

| Intent          | Tetikleyici                           | Yanıt stratejisi                    |
| --------------- | ------------------------------------- | ----------------------------------- |
| `greeting`      | Selamlama anahtar kelimeleri          | 2-3 cümle kısa karşılama            |
| `odoo_question` | Odoo anahtar kelimeleri / uzun soru   | RAG + ipuçları + kullanıcı bağlamı  |
| `unclear`       | Kısa, belirsiz                        | Hangi modül olduğunu sor            |

---

## Güvenlik & Yetkiler

| Grup                       | Yetki                                                       |
| -------------------------- | ----------------------------------------------------------- |
| `group_chatbot_user`       | Kendi sohbet oturumlarını okur ve yenisini oluşturur        |
| `group_chatbot_manager`    | Şirketteki tüm oturumları görür, siler, RAG indeksleyebilir |

Record rule'lar şirket ve kullanıcı izolasyonu uygular. Mesajlar düz metin
olarak saklanır, ekranda `t-esc` ile XSS güvenli render edilir.

---

## Sorun Giderme

### "İndeksleme tamamlandı ama 0 chunk eklendi"

Eski sürümdeki GitHub API rate-limit bug'ı. Sürüm `19.0.1.2.0` ile çözüldü:
indeksleme artık `git clone` üzerinden çalışıyor. Modülü güncellediğinizden
emin olun:

```powershell
venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo19_v1 ^
    -u odoo_help_assistant --stop-after-init
```

### "git komutu bulunamadı"

Git for Windows yükleyin ve PATH'e ekleyin: <https://git-scm.com/download/win>

### "Ollama servisine bağlanılamadı"

Ollama servisi çalışıyor mu?

```powershell
curl http://127.0.0.1:11434/api/tags
```

Modeller yüklü mü? `ollama list` ile kontrol edin.

### "nomic-embed-text bulunamadı"

```powershell
ollama pull nomic-embed-text
```

### Cevaplar yavaş geliyor

- Daha küçük model deneyin: `llama3.2:3b` (varsayılan)
- `max_tokens` değerini düşürün (örn. 250)
- Ollama'ya GPU verin (CPU çok yavaş kalır)

### Cevaplar Odoo dışına çıkıyor / yanlış

- RAG indeksinin dolu olduğundan emin olun: **İndeks Durumu** ekranına bakın
- Sistem prompt'unu sertleştirin: `Ayarlar → Yardım Asistanı → Sistem Prompt`
- `hint_layer_enabled` açık olsun

---

## Geliştirici Notları

### Testleri çalıştır

```powershell
venv\Scripts\python.exe odoo-bin -c odoo.conf -d odoo19_v1 ^
    --test-tags=odoo_help_assistant --stop-after-init
```

### Manifest sürüm geçmişi

| Sürüm        | Değişiklik                                                    |
| ------------ | ------------------------------------------------------------- |
| `19.0.1.2.0` | İndeksleme `git clone` tabanlıya geçti; per-section dağıtım; CLI script eklendi |
| `19.0.1.1.0` | RAG + `nomic-embed-text` desteği                              |
| `19.0.1.0.0` | İlk sürüm: Ollama + Owl arayüz + intent layer                 |

### Potansiyel geliştirmeler

- [ ] pgvector entegrasyonu (cosine similarity SQL'e taşınır)
- [ ] Ollama streaming (`stream: true`) — karakter karakter yanıt
- [ ] Uzun konuşma özetleme
- [ ] Otomatik yeniden indeksleme (cron job)
- [ ] llama.cpp provider'ı tamamla
- [ ] Beğen/beğenme geri bildirimi → prompt iyileştirme

---

## Lisans

LGPL-3

## Yazar

[Rasim Okutan](https://github.com/rasimokutan) — tez projesi kapsamında
geliştirilmiştir.
