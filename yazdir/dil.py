"""Arayüz dili (Türkçe / English).

Bütün kullanıcıya görünen metinler burada, anahtar -> {dil: metin}. Kod içinde t("anahtar", ...) ile
alınır; {ad} yer tutucuları str.format ile doldurulur. Seçilen dil ayarlarda ("dil") saklanır;
ayar yoksa sistem dili (LANG) kullanılır: tr ise Türkçe, değilse İngilizce.
"""
import os

DILLER = {"tr": "Türkçe", "en": "English"}
_aktif = "tr"


def sistem_dili() -> str:
    for d in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(d, "")
        if v:
            return "tr" if v.lower().startswith("tr") else "en"
    return "en"


def ayarla(kod: str | None) -> str:
    global _aktif
    _aktif = kod if kod in DILLER else sistem_dili()
    return _aktif


def aktif() -> str:
    return _aktif


def t(anahtar: str, **kw) -> str:
    m = METINLER[anahtar]
    s = m.get(_aktif) or m["tr"]
    return s.format(**kw) if kw else s


METINLER = {
    # ------------------------------------------------------------ düzenler
    "duzen.1": {"tr": "Her yüze 1 sayfa", "en": "1 page per side"},
    "duzen.2": {"tr": "Her yüze 2 sayfa (yan yana)", "en": "2 pages per side (side by side)"},
    "duzen.4": {"tr": "Her yüze 4 sayfa", "en": "4 pages per side"},
    "duzen.kitapcik": {"tr": "Kitapçık (A5, ortadan katlanır)", "en": "Booklet (A5, folded in the middle)"},

    # ------------------------------------------------------------ çekirdek hataları
    "hata.dosya_yok": {"tr": "Dosya bulunamadı: {yol}", "en": "File not found: {yol}"},
    "hata.libreoffice": {"tr": "LibreOffice dönüştüremedi: {ayrinti}", "en": "LibreOffice could not convert the file: {ayrinti}"},
    "hata.resim": {"tr": "Resim PDF'e çevrilemedi: {ayrinti}", "en": "Could not convert the image to PDF: {ayrinti}"},
    "hata.tur": {"tr": "Desteklenmeyen dosya türü: {ext}", "en": "Unsupported file type: {ext}"},
    "hata.aralik_anlasilmadi": {"tr": "Sayfa aralığı anlaşılamadı: '{parca}' (örnek: 1-5,8,10-)",
                                "en": "Could not read page range '{parca}' (example: 1-5,8,10-)"},
    "hata.aralik_gecersiz": {"tr": "Geçersiz sayfa aralığı: '{parca}' (belge {toplam} sayfa)",
                             "en": "Invalid page range '{parca}' (the document has {toplam} pages)"},
    "hata.duzen": {"tr": "Düzen şunlardan biri olmalı: {liste}", "en": "Layout must be one of: {liste}"},
    "hata.is_yok": {"tr": "Hazırlanmış iş yok. Önce 'yazdir hazirla DOSYA' çalıştırın.",
                    "en": "No prepared job. Run 'yazdir hazirla FILE' first."},
    "hata.is_bulunamadi": {"tr": "İş bulunamadı: {id}", "en": "Job not found: {id}"},
    "hata.gonderilemedi": {"tr": "Yazıcıya gönderilemedi: {ayrinti}", "en": "Could not send to the printer: {ayrinti}"},
    "hata.yazici_yok": {"tr": "Yazıcı bulunamadı.", "en": "No printer found."},
    "hata.arkali_is": {"tr": "Bu iş arkalı önlü; önce 'on', sonra 'arka' basılmalı.",
                       "en": "This is a two-sided job; print 'on' (fronts) first, then 'arka' (backs)."},
    "hata.tek_yuz_is": {"tr": "Bu iş tek yüz; 'hepsi' kullanın.", "en": "This is a one-sided job; use 'hepsi'."},
    "hata.arka_yok": {"tr": "Bu işin arka yüzü yok.", "en": "This job has no back sides."},
    "hata.adim": {"tr": "Bilinmeyen adım: {adim}", "en": "Unknown step: {adim}"},
    "hata.pycups": {"tr": "pycups bulunamadı. Kurun: Arch 'python-pycups', Debian/Ubuntu 'python3-cups'.",
                    "en": "pycups is missing. Install it: Arch 'python-pycups', Debian/Ubuntu 'python3-cups'."},
    "hata.cups_baglanti": {"tr": "CUPS'a bağlanılamadı ({ayrinti}). CUPS çalışıyor mu? (systemctl status cups)",
                           "en": "Could not connect to CUPS ({ayrinti}). Is CUPS running? (systemctl status cups)"},
    "hata.kuyruk_dolu": {"tr": "Yazıcı kuyruğunda bekleyen iş var. Önce kuyruğu temizleyin ya da bitmesini bekleyin.",
                         "en": "There are jobs waiting in the printer queue. Clear the queue or wait for them to finish."},

    # ------------------------------------------------------------ iş özeti
    "ozet.is": {"tr": "İş: {id}", "en": "Job: {id}"},
    "ozet.kaynak": {"tr": "Kaynak: {yol} ({toplam} sayfa, {secilen} sayfa seçildi)",
                    "en": "Source: {yol} (pages: {toplam}, selected: {secilen})"},
    "ozet.duzen": {"tr": "Düzen: {ad}", "en": "Layout: {ad}"},
    "ozet.kopya": {"tr": ", {n} kopya", "en": ", copies: {n}"},
    "ozet.baski_arkali": {"tr": "Baskı: elle arkalı önlü — {yuz} yüz, {kagit} kâğıt",
                          "en": "Printing: manual two-sided — sides: {yuz}, sheets: {kagit}"},
    "ozet.baski_tek": {"tr": "Baskı: tek yüz — {yuz} yüz, {kagit} kâğıt",
                       "en": "Printing: one-sided — sides: {yuz}, sheets: {kagit}"},
    "ozet.yazici": {"tr": "Yazıcı: {ad}", "en": "Printer: {ad}"},
    "ozet.adimlar": {"tr": "Adım 1: {on} ön yüz • Adım 2: {arka} arka yüz (ters sırayla)",
                     "en": "Step 1: fronts ({on}) • Step 2: backs ({arka}, in reverse order)"},
    "ozet.bos_arka": {"tr": "Not: Son kâğıdın arkası boş kalacak (kâğıt ayırmaya gerek yok).",
                      "en": "Note: the last sheet's back stays blank (no need to take any sheet out)."},
    "ozet.son_kagidi_ayir": {"tr": "Not: Son kâğıdın arkası boş kalacak; arka yüzden önce o kâğıt ayrılmalı.",
                             "en": "Note: the last sheet's back stays blank; take that sheet out before printing the backs."},
    "ozet.durum": {"tr": "Durum: {durum}", "en": "Status: {durum}"},
    "durum.hazir": {"tr": "hazır", "en": "ready"},
    "durum.on_basildi": {"tr": "ön yüzler basıldı", "en": "fronts printed"},
    "durum.bitti": {"tr": "bitti", "en": "done"},
    "durum.hepsi_gonderildi": {"tr": "yazıcıya gönderildi", "en": "sent to the printer"},
    "durum.on_gonderildi": {"tr": "ön yüzler yazıcıya gönderildi", "en": "fronts sent to the printer"},
    "durum.arka_gonderildi": {"tr": "arka yüzler yazıcıya gönderildi", "en": "backs sent to the printer"},
    "durum.vazgecildi": {"tr": "yarıda bırakıldı", "en": "abandoned"},

    # ------------------------------------------------------------ yazıcı uyarıları (baskı sürerken)
    "uyari.kagit_yok": {"tr": "Yazıcı 'kâğıt yok' diyor. Kâğıdı çıkarıp düzgünce yeniden yerleştirin; olmazsa yazıcıyı "
                              "kapatıp açın. Baskı bekliyor, kâğıt algılanınca kendiliğinden devam eder.",
                        "en": "The printer reports 'out of paper'. Take the paper out and load it again neatly; if that does "
                              "not help, switch the printer off and on. The job is waiting and continues by itself."},
    "uyari.kagit_sikisti": {"tr": "Kâğıt sıkıştı. Sıkışan kâğıdı dikkatlice çıkarın; baskı sonra devam eder.",
                            "en": "Paper jam. Carefully remove the jammed paper; printing then continues."},
    "uyari.kapak_acik": {"tr": "Yazıcının kapağı açık. Kapatınca baskı devam eder.",
                         "en": "The printer cover is open. Printing continues once it is closed."},
    "uyari.toner": {"tr": "Toner bitmiş görünüyor.", "en": "The toner seems to be empty."},
    "uyari.baglanti_yok": {"tr": "Yazıcıya ulaşılamıyor. USB kablosunu ve yazıcının açık olduğunu kontrol edin; "
                                 "bağlanınca baskı kendiliğinden devam eder.",
                           "en": "The printer cannot be reached. Check the USB cable and that the printer is on; "
                                 "printing continues by itself once it is connected."},
    "uyari.yazici_durdu": {"tr": "Yazıcı CUPS'ta durdurulmuş. Kabloyu ve gücü kontrol edin; uygulama yazıcıyı "
                                 "yarım dakikada bir yeniden başlatmayı deniyor.",
                           "en": "The printer is stopped in CUPS. Check the cable and power; the app tries to "
                                 "restart it every half minute."},

    # ------------------------------------------------------------ kâğıdı geri koyma talimatı
    "talimat.nasil": {"tr": "yönünü değiştirmeden (çevirmeden, döndürmeden), basılı yüzü aşağıda tepsiye geri koyun.",
                      "en": "back in the tray without changing their orientation (do not flip or rotate them), printed side down."},
    "talimat.eski": {"tr": "Ön yüzler basıldı. Önce tomarın EN ÜSTÜNDEKİ (en son basılan) kâğıdı ayırın — onun arkası "
                           "boş kalacak. Kalan {n} kâğıdı ",
                     "en": "The fronts are printed. First take out the TOP sheet of the stack (the last one printed) — "
                           "its back stays blank. Put the remaining sheets ({n}) "},
    "talimat.hepsi": {"tr": "Ön yüzler basıldı. Çıkan {n} kâğıdın HEPSİNİ ",
                      "en": "The fronts are printed. Put ALL the sheets ({n}) "},
    "talimat.bos_arka": {"tr": " Boş kâğıt ayırmayın: en son basılan kâğıt arkası boş olarak geçecek.",
                         "en": " Do not take any sheet out: the last printed sheet will pass through with a blank back."},

    # ------------------------------------------------------------ yön deneme sayfası
    "deneme.ust": {"tr": "ÜST", "en": "TOP"},
    "deneme.on": {"tr": "ÖN YÜZ", "en": "FRONT"},
    "deneme.arka": {"tr": "ARKA YÜZ", "en": "BACK"},
    "deneme.soru": {"tr": "Kâğıdı kitap sayfası çevirir gibi yan kenarından çevirin.\n"
                          "Ön yüzdeki ok yukarıyı gösterirken arka yüzdeki ok da YUKARIYI gösteriyor mu?",
                    "en": "Turn the sheet over by its side edge, like turning a book page.\n"
                          "With the front arrow pointing up, does the arrow on the back point UP as well?"},

    # ------------------------------------------------------------ pencere
    "gui.baslik": {"tr": "Yazdır", "en": "Manual Duplex Print"},
    "gui.dil": {"tr": "Dil:", "en": "Language:"},
    "gui.dosya_yok": {"tr": "Dosya seçilmedi — dosyayı buraya sürükleyebilirsiniz.",
                      "en": "No file selected — you can drag a file here."},
    "gui.dosya_sec": {"tr": "Dosya Seç…", "en": "Choose File…"},
    "gui.dosya_diyalog": {"tr": "Yazdırılacak dosya", "en": "File to print"},
    "gui.uzantilar": {"tr": "Belgeler ({desen});;Tüm dosyalar (*)", "en": "Documents ({desen});;All files (*)"},
    "gui.arkali": {"tr": "Arkalı önlü (elle çevirerek)", "en": "Two-sided (turning the paper by hand)"},
    "gui.sayfalar_ipucu": {"tr": "Tümü  (ör. 1-5, 8, 10-)", "en": "All  (e.g. 1-5, 8, 10-)"},
    "gui.yazici": {"tr": "Yazıcı:", "en": "Printer:"},
    "gui.sayfalar": {"tr": "Sayfalar:", "en": "Pages:"},
    "gui.kopya": {"tr": "Kopya:", "en": "Copies:"},
    "gui.sayfa_duzeni": {"tr": "Sayfa düzeni", "en": "Page layout"},
    "gui.yazdir": {"tr": "Yazdır", "en": "Print"},
    "gui.kuyrugu_temizle": {"tr": "Kuyruğu temizle", "en": "Clear queue"},
    "gui.arka_180": {"tr": 'Yazıcım arka yüzleri ters basıyor — düzelt',
                    "en": 'My printer prints back sides upside down — correct it'},
    "gui.arka_180_ipucu": {"tr": "Bu bir yazıcı ayarıdır, baskıyı ters çevirmez. Açıkken uygulama yazıcının ters basmasını telafi eder ve arka yüzler kâğıtta DÜZ çıkar. Emin değilseniz 'Yön deneme sayfası'nı basın.",
                          "en": "This is a printer setting; it does not flip your print. When on, the app compensates for the printer printing backs upside down, so the back sides come out UPRIGHT on paper. If unsure, print the 'Orientation test page'."},
    "gui.arka_180_onay_ac": {"tr": "Bunu yalnızca yazıcınız arka yüzleri baş aşağı basıyorsa açın: uygulama bunu telafi eder, arka yüzler kâğıtta düz çıkar.\n\nEmin değilseniz önce 'Yön deneme sayfası'nı basın.\n\nDüzeltme açılsın mı?",
                            "en": "Turn this on only if your printer prints back sides upside down: the app compensates and the backs come out upright on paper.\n\nIf unsure, print the 'Orientation test page' first.\n\nTurn the correction on?"},
    "gui.arka_180_onay_kapat": {"tr": "Kapatırsanız arka yüzler düzeltme yapılmadan gönderilir; yazıcınız arka yüzleri ters basıyorsa kâğıtta baş aşağı çıkarlar.\n\nEmin değilseniz önce 'Yön deneme sayfası'nı basın.\n\nDüzeltme kapatılsın mı?",
                               "en": "If you turn this off, back sides are sent without correction; if your printer prints them upside down, they come out upside down on paper.\n\nIf unsure, print the 'Orientation test page' first.\n\nTurn the correction off?"},
    "gui.yon_acik": {"tr": "Açık: arka yüzler kâğıtta düz çıkacak şekilde düzeltiliyor.",
                     "en": "On: back sides are corrected so they come out upright."},
    "gui.yon_kapali": {"tr": "Kapalı: arka yüzler düzeltme yapılmadan gönderiliyor.",
                       "en": "Off: back sides are sent without correction."},
    "gui.yon_deneme_tarihi": {"tr": " Deneme sayfasıyla belirlendi ({tarih}).", "en": " Set with the test page ({tarih})."},
    "gui.deneme_btn": {"tr": "Yön deneme sayfası (1 kâğıt)", "en": "Orientation test page (1 sheet)"},
    "gui.yon_grubu": {"tr": "Arkalı önlü yönü", "en": "Two-sided orientation"},
    "gui.kuyrukta": {"tr": " • Kuyrukta {n} iş", "en": " • jobs in queue: {n}"},
    "gui.yazici_hazir": {"tr": "hazır", "en": "idle"},
    "gui.yazici_basiyor": {"tr": "yazdırıyor", "en": "printing"},
    "gui.yazici_kapali": {"tr": "devre dışı", "en": "disabled"},
    "gui.yazici_durum": {"tr": "Yazıcı {ad}: {durum}{kuyruk}", "en": "Printer {ad}: {durum}{kuyruk}"},
    "gui.hazirlaniyor": {"tr": "Hazırlanıyor…", "en": "Preparing…"},
    "gui.kagit_on": {"tr": "{n}. kâğıt — ön", "en": "Sheet {n} — front"},
    "gui.kagit_arka": {"tr": "{n}. kâğıt — arka", "en": "Sheet {n} — back"},
    "gui.kagit": {"tr": "{n}. kâğıt", "en": "Sheet {n}"},
    "gui.ozet_sayilar": {"tr": "{yuz} yüz, {kagit} kâğıt", "en": "Sides: {yuz} • Sheets: {kagit}"},
    "gui.ozet_arkali": {"tr": "Önce {on} ön yüz basılır, sonra kâğıtları geri koyduğunuzda {arka} arka yüz.",
                        "en": "First the fronts are printed ({on}), then the backs ({arka}) after you put the sheets back."},
    "gui.ozet_kitapcik": {"tr": "Kâğıtları sırayla iç içe koyup ortadan katlayın.",
                          "en": "Nest the sheets in order and fold them in the middle."},
    "gui.deneme_baslik": {"tr": "Yön deneme sayfası", "en": "Orientation test page"},
    "gui.yon_denemesi": {"tr": "Yön denemesi", "en": "Orientation test"},
    "gui.ayar_dogru": {"tr": "Ayar doğru, değiştirilmedi.", "en": "The setting is correct; nothing changed."},
    "gui.ayar_180": {"tr": 'Kaydedildi: yazıcınız arka yüzleri ters basıyor. Uygulama bundan sonra bunu düzeltecek; arka yüzler kâğıtta düz çıkacak.',
                    "en": 'Saved: your printer prints back sides upside down. The app will correct this from now on; back sides will come out upright.'},
    "gui.ayar_duz": {"tr": 'Kaydedildi: yazıcınız arka yüzleri düz basıyor, düzeltme kapatıldı.',
                    "en": 'Saved: your printer prints back sides upright; the correction is off.'},
    "gui.on_yuzler": {"tr": "Ön yüzler", "en": "Fronts"},
    "gui.on_soru": {"tr": "Tepsiye en az {kagit} boş kâğıt koyun.\n\n1. adım: {on} ön yüz basılacak. Başlansın mı?",
                    "en": "Put blank paper in the tray (at least {kagit} sheets).\n\nStep 1: the fronts will be printed ({on}). Start?"},
    "gui.tek_soru": {"tr": "{kagit} kâğıt basılacak. Başlansın mı?", "en": "Sheets to print: {kagit}. Start?"},
    "gui.on_basiliyor": {"tr": "Ön yüzler basılıyor…", "en": "Printing fronts…"},
    "gui.arka_basiliyor": {"tr": "Arka yüzler basılıyor…", "en": "Printing backs…"},
    "gui.basiliyor": {"tr": "Basılıyor…", "en": "Printing…"},
    "gui.mesgul": {"tr": "Başka bir işlem sürüyor; birkaç saniye sonra yeniden deneyin.",
                   "en": "Another operation is running; try again in a few seconds."},
    "gui.bitti": {"tr": "Baskı tamamlandı.", "en": "Printing finished."},
    "gui.bitti_kitapcik": {"tr": "\n\nKitapçık: kâğıtları sırayla iç içe koyup ortadan katlayın.",
                           "en": "\n\nBooklet: nest the sheets in order and fold them in the middle."},
    "gui.cevir_baslik": {"tr": "Kâğıtları çevirin", "en": "Reload the paper"},
    "gui.on_basildi": {"tr": "Ön yüzler basıldı.", "en": "The fronts are printed."},
    "gui.hazir_olunca": {"tr": "\n\nHazır olunca 'Devam'a basın.", "en": "\n\nWhen ready, press 'Continue'."},
    "gui.devam": {"tr": "Devam — arka yüzleri bas", "en": "Continue — print the backs"},
    "gui.vazgec": {"tr": "Vazgeç", "en": "Cancel"},
    "gui.kuyruk": {"tr": "Kuyruk", "en": "Queue"},
    "gui.kuyruk_soru": {"tr": "Yazıcı kuyruğundaki tüm işler iptal edilsin mi?",
                        "en": "Cancel all jobs in the printer queue?"},
    "gui.uyari_baslik": {"tr": "Yazıcı uyarısı", "en": "Printer warning"},
    "gui.iptal_edildi": {"tr": "Baskı iptal edildi.", "en": "Printing was cancelled."},
    "gui.baski_hatasi": {"tr": "Baskı yazıcıda başarısız oldu ({neden}).\n\nYazıcıyı kontrol edip yeniden deneyin. "
                               "Ayrıntı: {gunluk}",
                         "en": "Printing failed at the printer ({neden}).\n\nCheck the printer and try again. "
                               "Details: {gunluk}"},
    "gui.kapat_soru": {"tr": "Baskı sürüyor. Pencereyi kapatırsanız yazıcı basmaya devam eder; uygulamayı yeniden "
                             "açtığınızda kaldığı yerden devam edebilirsiniz.\n\nKapatılsın mı?",
                       "en": "Printing is in progress. If you close the window the printer keeps printing; when you open "
                             "the app again you can continue where you left off.\n\nClose?"},
    "gui.yarim_baslik": {"tr": "Yarım kalan baskı", "en": "Unfinished print job"},
    "gui.yarim_arka": {"tr": "Önceki baskının arka yüzleri basılmadı:\n{dosya}\n\nŞimdi arka yüzlere devam edilsin mi?",
                       "en": "The back sides of the previous job were not printed:\n{dosya}\n\nContinue with the backs now?"},
    "gui.yarim_suruyor": {"tr": "Önceki baskı uygulama kapalıyken sürüyordu:\n{dosya}\n\nİzlemeye devam edilsin mi?",
                          "en": "The previous job was still printing when the app was closed:\n{dosya}\n\nKeep following it?"},
    "gui.beklenmeyen": {"tr": "Beklenmeyen bir hata oldu:\n{hata}\n\nAyrıntı günlükte: {gunluk}",
                        "en": "An unexpected error occurred:\n{hata}\n\nDetails are in the log: {gunluk}"},
    "gui.dil_mesgul": {"tr": "Baskı sürerken dil değiştirilemez.", "en": "The language cannot be changed while printing."},

    # ------------------------------------------------------------ komut satırı
    "cli.aciklama": {"tr": "Elle arkalı önlü, çoklu sayfa ve kitapçık baskısı.",
                     "en": "Manual two-sided, n-up and booklet printing."},
    "cli.yardim": {"tr": """yazdir — komut satırı.

  yazdir hazirla DOSYA [-d 1|2|4|kitapcik] [-a] [-s 1-5,8] [-k 2] [-y YAZICI]
  yazdir onizle [IS]            önizleme PNG'lerini üretir, yollarını yazar
  yazdir bilgi [IS]             işin özeti
  yazdir bas [IS] hepsi|on|arka --onayli   iş adımını yazıcıya gönderir (bitene kadar bekler)
  yazdir deneme                 arka yüz yön denemesi (1 kâğıt) hazırlar; sonra bas on / bas arka
  yazdir deneme-sonucu evet|hayir   arka yüzdeki ok yukarıyı gösterdi mi? ayarı buna göre kaydeder
  yazdir durum                  yazıcı durumu, kuyruk, son hatalar
  yazdir temizle                kuyruktaki tüm işleri iptal eder, yazıcıyı etkinleştirir
  yazdir yazicilar              yazıcıları listeler
  yazdir varsayilan YAZICI      varsayılan yazıcıyı kaydeder
  yazdir dil tr|en              arayüz dilini seçer
IS verilmezse son hazırlanan iş kullanılır. --json ile makine okunur çıktı.""",
                  "en": """yazdir — command line.

  yazdir hazirla FILE [-d 1|2|4|kitapcik] [-a] [-s 1-5,8] [-k 2] [-y PRINTER]   prepare (does not print)
  yazdir onizle [JOB]           renders preview PNGs, prints their paths
  yazdir bilgi [JOB]            job summary
  yazdir bas [JOB] hepsi|on|arka --onayli   sends a step to the printer (all | fronts | backs), waits
  yazdir deneme                 prepares the back-side orientation test (1 sheet); then bas on / bas arka
  yazdir deneme-sonucu evet|hayir   did the arrow on the back point up (yes|no)? saves the setting
  yazdir durum                  printer status, queue, recent errors
  yazdir temizle                cancels all queued jobs, re-enables the printer
  yazdir yazicilar              lists printers
  yazdir varsayilan PRINTER     saves the default printer
  yazdir dil tr|en              selects the interface language
Without JOB the most recently prepared job is used. --json gives machine-readable output."""},
    "cli.h.json": {"tr": "JSON çıktı", "en": "JSON output"},
    "cli.h.hazirla": {"tr": "belgeyi baskıya hazırla (yazdırmaz)", "en": "prepare a document (does not print)"},
    "cli.h.onizleme": {"tr": "hazırlarken önizleme de üret", "en": "also render previews"},
    "cli.h.bas": {"tr": "iş adımını yazdır", "en": "print a job step"},
    "cli.h.onayli": {"tr": "kullanıcı açıkça 'bas' dedi; bu bayrak olmadan hiçbir şey yazıcıya gönderilmez",
                     "en": "the user explicitly asked to print; nothing is sent to the printer without this flag"},
    "cli.h.deneme": {"tr": "arka yüz yön deneme sayfası hazırla", "en": "prepare the back-side orientation test page"},
    "cli.h.deneme_sonucu": {"tr": "deneme sayfasının arka yüzü doğru mu çıktı", "en": "was the test page's back side correct"},
    "cli.h.dil": {"tr": "arayüz dilini seç", "en": "select the interface language"},
    "cli.bitti": {"tr": "Baskı tamamlandı.", "en": "Printing finished."},
    "cli.gonderildi": {"tr": "Yazıcıya gönderildi.", "en": "Sent to the printer."},
    "cli.sonra_arka": {"tr": "Sonra (yeni onayla): yazdir bas {id} arka --onayli",
                       "en": "Then (with a new confirmation): yazdir bas {id} arka --onayli"},
    "cli.onay_yok": {"tr": "Yazdırılmadı: 'bas' için --onayli gerekir (kullanıcı onayı). İş {id}, adım '{adim}'.",
                     "en": "Not printed: 'bas' needs --onayli (user confirmation). Job {id}, step '{adim}'."},
    "cli.onizleme": {"tr": "Önizleme:", "en": "Preview:"},
    "cli.deneme_sonra": {"tr": "Onay sonrası: yazdir bas on --onayli, kâğıdı geri koyup yazdir bas arka --onayli.",
                         "en": "After confirmation: yazdir bas on --onayli, put the sheet back, then yazdir bas arka --onayli."},
    "cli.deneme_cevap": {"tr": "Cevap: yazdir deneme-sonucu evet|hayir", "en": "Answer: yazdir deneme-sonucu evet|hayir (yes|no)"},
    "cli.kaydedildi_180": {"tr": 'Kaydedildi: yazıcı arka yüzleri ters basıyor; uygulama düzeltecek, arka yüzler düz çıkacak.',
                          "en": 'Saved: the printer prints backs upside down; the app will correct it, backs come out upright.'},
    "cli.kaydedildi_duz": {"tr": 'Kaydedildi: yazıcı arka yüzleri düz basıyor; düzeltme kapalı.',
                          "en": 'Saved: the printer prints backs upright; correction is off.'},
    "cli.iptal": {"tr": "Baskı iptal edildi.", "en": "Printing was cancelled."},
    "cli.hata_sonuc": {"tr": "Baskı yazıcıda başarısız oldu ({neden}).", "en": "Printing failed at the printer ({neden})."},
    "cli.uyari": {"tr": "UYARI: {m}", "en": "WARNING: {m}"},
    "cli.uyari_kalkti": {"tr": "Sorun giderildi, baskı sürüyor.", "en": "Problem cleared, printing continues."},
    "cli.uyarilar": {"tr": "Uyarılar: {x}", "en": "Alerts: {x}"},
    "cli.kuyruk": {"tr": "Kuyruk: {x}", "en": "Queue: {x}"},
    "cli.bos": {"tr": "boş", "en": "empty"},
    "cli.son_hatalar": {"tr": "Son hatalar:", "en": "Recent errors:"},
    "cli.temizlendi": {"tr": "Kuyruk temizlendi.", "en": "Queue cleared."},
    "cli.varsayilan": {"tr": "Varsayılan yazıcı: {ad}", "en": "Default printer: {ad}"},
    "cli.dil": {"tr": "Dil: Türkçe", "en": "Language: English"},
    "cli.hata": {"tr": "HATA: {m}", "en": "ERROR: {m}"},
}
