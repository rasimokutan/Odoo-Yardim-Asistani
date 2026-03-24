# Odoo Yardım Asistanı

Bu proje, Odoo 19 Community içinde çalışan basit bir yapay zekâ destekli sohbet modülüdür.

Amaç şu:
Odoo kullanan biri ekranda takıldığında, "Bunu nereden yapacağım?", "Hangi menüye girmeliyim?", "Bu işlem neden olmuyor?" gibi sorular sorabilsin ve modül de Türkçe şekilde yardımcı olsun.

Ben bu modülü özellikle son kullanıcıya ve Odoo operatörlerine yardım etmesi için hazırladım. Yani bu modül kod üreten bir araç değil. Daha çok Odoo kullanımını anlatan bir yardımcı gibi düşünmek lazım.

## Ne işe yarıyor?

Bu modülle kullanıcı Odoo içinde bir sohbet ekranı açabiliyor ve mesela şunları sorabiliyor:

- Satış teklifi nasıl onaylanır?
- Stok transferinde Doğrula butonu neden görünmüyor?
- Faturayı ödeme ile nasıl eşleştiririm?
- CRM fırsatında aktiviteyi nereden eklerim?
- Satın alma siparişini hangi menüden bulurum?

Modül cevapları Türkçe vermeye çalışır.

## Öne çıkan özellikler

- Odoo içinde çalışan sohbet ekranı
- Türkçe odaklı cevaplar
- Ollama ile yerel çalışma
- Sohbet oturumu oluşturma
- Mesaj geçmişini Odoo içinde saklama
- Yönetici için geçmiş sohbetleri görme ekranı
- Ayarlar kısmından model, URL, timeout gibi alanları değiştirebilme
- Odoo satış, stok, muhasebe, CRM gibi başlıklarda küçük ipucu katmanı

## Kullanılan yapı

Bu modülde ana yapay zekâ sağlayıcısı olarak Ollama kullanılıyor.

Yani mantık şu şekilde:

1. Kullanıcı Odoo içinde soru yazar.
2. Modül bu soruyu backend tarafında hazırlar.
3. İstek yerel Ollama servisine gider.
4. Gelen cevap tekrar Odoo ekranına yazılır.

Şu an ana hedef basit ve çalışan bir yapı kurmak olduğu için ekstra karmaşık şeyler eklenmedi.

Özellikle şunlar bu sürümde yok:

- RAG
- vektör veritabanı
- belge yükleyip analiz etme
- otomatik işlem yapan ajan sistemi
- tehlikeli otomasyonlar

## Klasör yapısı

Projede temel olarak şu bölümler var:

- `models/` : sohbet oturumu, mesajlar ve ayarlar
- `controllers/` : frontend ile backend konuşması
- `services/` : Ollama isteğini hazırlayan servis katmanı
- `views/` : menüler, ayar ekranı, yönetim ekranları
- `static/src/` : Owl arayüzü, şablonlar ve stil dosyaları
- `security/` : erişim hakları ve record rule tanımları
- `tests/` : temel testler

## Kurulum

### 1. Modülü addons path içine koyun

Bu modül genelde şöyle bir yere konur:

```python
custom_addons/odoo_help_assistant
```

Sonra `odoo.conf` içinde bu klasörün `addons_path` içine dahil olduğundan emin olun.

### 2. Uygulama listesini yenileyin

Odoo içinde geliştirici modunu açın.

Ardından uygulama listesini yenileyin.

### 3. Modülü yükleyin

Uygulamalar ekranında:

`Odoo Yardım Asistanı`

modülünü yükleyin.

## Güncelleme

Kod değişikliği yaptıktan sonra genelde şu komut yeterli olur:

```bash
odoo-bin -d <veritabanı_adı> -u odoo_help_assistant --stop-after-init
```

Sonra Odoo’yu tekrar başlatıp tarayıcıda `Ctrl+F5` yapmak iyi olur.

Frontend dosyası değiştiyse bazen şu şekilde açmak da işe yarar:

```text
http://localhost:8069/web?debug=assets
```

## Ollama kurulumu

## Windows

Ollama’yı şu adresten kurabilirsiniz:

https://ollama.com/download

Kurulumdan sonra çoğu durumda Ollama arka planda zaten açık olur.

## Linux / macOS

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

## Model indirme

İlk deneme için hafif bir model kullanmak daha rahat olur.

Örnek:

```bash
ollama pull llama3.2:3b
```

Alternatif:

```bash
ollama pull qwen2.5:3b
```

## Ollama çalışıyor mu nasıl anlarım?

Şu komutla yüklü modelleri görebilirsiniz:

```bash
ollama list
```

Modeli direkt test etmek için:

```bash
ollama run llama3.2:3b
```

Eğer terminalde cevap üretiyorsa büyük ihtimalle servis düzgündür.

Bir de HTTP tarafını test etmek isterseniz:

```bash
curl http://127.0.0.1:11434/api/tags
```

Bu istek cevap veriyorsa Odoo da aynı adrese bağlanabilir.

## Önemli not

Bazı Windows kurulumlarında `ollama serve` komutunu tekrar çalıştırınca şu hata gelir:

`Only one usage of each socket address ... is normally permitted`

Bu genelde kötü bir şey değildir.
Çoğu zaman sadece şu anlama gelir:

Ollama zaten çalışıyor.

Yani bu hatayı görünce önce tekrar servis açmaya çalışmak yerine `ollama list` veya `curl http://127.0.0.1:11434/api/tags` ile kontrol etmek daha doğru olur.

## Odoo ayarları nasıl olmalı?

`Ayarlar > Odoo Yardım Asistanı` bölümünde genel olarak şu değerler iş görür:

- Yardım asistanı aktif: açık
- LLM sağlayıcısı: Ollama
- Ollama adresi: `http://127.0.0.1:11434`
- Model adı: `llama3.2:3b`
- Yaratıcılık seviyesi: `0.2`
- Azami cevap uzunluğu: `300`
- Zaman aşımı: `45`

## Dikkat edilmesi gereken şey

URL yanlış yazılırsa modül cevap üretemez.

Doğru örnek:

```text
http://127.0.0.1:11434
```

Yanlış örnek:

```text
http://127.0.0.1:111434
```

Port yanlışsa bağlantı kurulamaz.

## Modül nasıl kullanılır?

1. Odoo içinde `Yardım Asistanı > Sohbet` menüsüne girin.
2. `Yeni Sohbet` butonuna tıklayın.
3. Sorunuzu yazın.
4. Asistan cevap versin.

Örnek sorular:

- Satış teklifini nasıl onaylarım?
- Müşteri ödemesini faturaya nasıl bağlarım?
- Stok transferi neden beklemede kaldı?
- Muhasebede taslak kayıtları nereden görebilirim?

## Sorun giderme

### 1. Sohbet ekranı açılıyor ama cevap gelmiyor

Şunları kontrol edin:

- Ollama gerçekten çalışıyor mu?
- Odoo ayarındaki URL doğru mu?
- Model adı doğru mu?
- Model gerçekten bilgisayarda yüklü mü?

Kontrol komutları:

```bash
ollama list
ollama run llama3.2:3b
```

### 2. “Yardım asistanı pasif durumda” uyarısı

Genelde ayar kaydedilmemiş olabilir.

Şunları yapın:

1. Ayarlara girin
2. Yardım asistanı aktif kutusunu kontrol edin
3. Kaydedin
4. Modülü güncellediyseniz tarayıcıyı yenileyin

### 3. Yeni sohbet oluştururken hata

Bu durumda genelde:

- modül güncellemesi yapılmamıştır
- eski asset dosyası çalışıyordur
- tarayıcı cache’te eski JS kalmıştır

Yapılacaklar:

```bash
odoo-bin -d <veritabanı_adı> -u odoo_help_assistant --stop-after-init
```

Sonra:

- Odoo’yu yeniden başlatın
- `?debug=assets` ile açın
- `Ctrl+F5` yapın

### 4. Ollama bağlantı hatası

Beklenen doğru adres çoğu yerel kurulumda şudur:

```text
http://127.0.0.1:11434
```

Eğer Odoo başka ortamda çalışıyorsa bu adres değişebilir ama masaüstü geliştirme için çoğunlukla bu yeterlidir.

## Geliştirme notları

Bu proje özellikle aşırı karmaşık yapılmadı.

İsteyerek basit bırakılan şeyler var:

- prompt yapısı sade
- ek bilgi katmanı küçük tutuldu
- servis katmanı ileride genişletilebilir şekilde bırakıldı

İleride yapılabilecek geliştirmeler:

- Ayarlara “bağlantıyı test et” butonu eklemek
- llama.cpp uyumlu provider eklemek
- daha iyi mesaj formatlama
- Odoo ekran bağlamını daha iyi yakalamak
- daha iyi hata ekranları

## Test

Temel testleri çalıştırmak için:

```bash
odoo-bin -d <veritabanı_adı> --test-enable --stop-after-init -i odoo_help_assistant
```

## Son söz

Bu modül mükemmel bir ürün gibi değil, çalışan ve geliştirilmeye açık bir yardımcı araç gibi düşünüldü.

Benim hedefim şuydu:
Odoo içinde gerçekten işe yarayan, yerel çalışan, Türkçe odaklı ve uğraştırmayan bir yardımcı sohbet modülü çıkarmak.

Eğer geliştirirken Odoo’da yeniyseniz, bu proje kurcalamak ve öğrenmek için de güzel bir örnek olabilir.
