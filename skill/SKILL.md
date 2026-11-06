---
name: yazdir
description: Kullanıcının yazıcısından (HP LaserJet 1018, otomatik arkalı önlü yok) belge yazdırmak için. PDF/Word/resim dosyasını tek yüz, elle arkalı önlü, kâğıt başına 2 ya da 4 sayfa veya A5 kitapçık olarak basmak, yazıcı kuyruğunu/kağıt hatasını kontrol etmek gerektiğinde kullan. "yazdır", "bas", "arkalı önlü", "kitapçık", "1 sayfaya 2 sayfa", "yazıcı kağıt yok diyor" gibi isteklerde.
---

# yazdir aracı

Kod: bu depo (`install.sh` ile kurulur) · Komut: `yazdir` (`~/.local/bin/yazdir`) · Pencereli sürüm: `yazdir-gui [DOSYA]`

## Kesin kural
**Kullanıcı sohbette açıkça "bas" (ya da aynı anlamda bir onay) demeden `yazdir bas` çalıştırma.** Test sayfası dahil.
Test ederken bile `bas` çalıştırma (bir kez yanlışlıkla kâğıt basıldı). Hazırlamak, önizlemek, durum bakmak serbest; kâğıda dokunan her adım için onay al. Her `bas` adımı için ayrı onay gerekir
(ön yüz onayı arka yüzü kapsamaz).

## Akış
1. Hazırla (yazdırmaz):
   ```bash
   yazdir hazirla DOSYA -d 2 -a --onizleme      # 1 sayfaya 2 sayfa, arkalı önlü
   yazdir hazirla DOSYA -d kitapcik --onizleme  # A5 kitapçık (otomatik arkalı önlü)
   yazdir hazirla DOSYA -s 1-5,8 -k 2           # sayfa seçimi, 2 kopya, tek yüz
   ```
   `-d`: `1` (varsayılan), `2` (yatay A4'e yan yana 2), `4` (2×2), `kitapcik`. `-a`: elle arkalı önlü.
   Çıktıda iş kimliği, yüz/kâğıt sayısı ve adımlar yazar. `--json` makine okunur çıktı verir.
2. Önizleme PNG'lerinden ilkini/birkaçını `Read` ile kontrol et; kullanıcıya özetle (kaç kâğıt, hangi düzen).
3. Kullanıcıya tepsiye kaç kâğıt koyacağını söyle, "bas" demesini bekle.
4. Tek yüz: `yazdir bas hepsi --onayli` · Arkalı önlü: `yazdir bas on --onayli` → çıktıdaki talimatı kullanıcıya ilet
   (tomarın HEPSİNİ yönünü değiştirmeden, basılı yüzü aşağıda geri koyacak; kâğıt ayırmayacak — yüz sayısı
   tekse son kâğıt arkası boş geçer) →
   yeni "bas" onayı → `yazdir bas arka --onayli`. `bas` bitene kadar bekler; çıkış kodu 2 = kağıt yok/zaman aşımı.
5. Kitapçık: kâğıtlar sırayla iç içe konup ortadan katlanır.

## Dil
Arayüz ve mesajlar Türkçe ya da İngilizce olabilir (`yazdir dil tr|en`, pencerede sağ üstte "Dil").
Kullanıcıyla Türkçe konuşuyorsan ve çıktı İngilizce geliyorsa `yazdir dil tr` çalıştır.

## Arka yüz yönü
2'li sayfa ve kitapçıkta arka yüzler kendiliğinden 180° döndürülür (Windows sürücüsü de böyle yapar).
Kullanıcı "arka sayfalar ters/baş aşağı çıkıyor" derse: `yazdir deneme` (1 kâğıt) → onayla `bas on` / `bas arka` →
kullanıcıya oku sor → `yazdir deneme-sonucu evet|hayir` (ayar `~/.config/yazdir/config.json` → `arka_180`).

## Sorun giderme
- `yazdir durum` → yazıcı, kuyruk, son CUPS hataları.
- `media-empty-error` (kırmızı ışık, kağıt varken bile): kullanıcı kağıdı çıkarıp düzgünce yeniden koysun, gerekirse
  yazıcıyı kapatıp açsın. İş kuyrukta bekler. Takılırsa `yazdir temizle` (tüm işleri iptal eder) — bunu da kullanıcıya söyleyerek yap.
- `bas`, kuyrukta başka iş varsa çalışmaz; önce durumu kontrol et.
- Neden elle: yazıcıda dupleks ünitesi yok (PPD: Duplexer Installed=False), "arkalı önlü" seçeneği yok sayılır.
