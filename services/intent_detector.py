_GREETING_KEYWORDS = frozenset({
    "merhaba", "selam", "iyi günler", "iyi sabahlar", "iyi akşamlar",
    "hey", "hi", "hello", "naber", "nasılsın", "nasılsınız", "günaydın",
    "tunaydin", "tünaydın", "teşekkür", "tesekkurler", "sağ ol", "sagol",
    "bay bay", "görüşürüz", "hoşça kal", "eyvallah", "tamam", "anladım",
})

_ODOO_KEYWORDS = frozenset({
    "odoo", "satış", "satis", "satinalma", "satın", "stok", "envanter",
    "fatura", "muhasebe", "crm", "müşteri", "musteri", "tedarikçi",
    "tedarikci", "sipariş", "siparis", "teklif", "transfer", "depo",
    "ürün", "urun", "kullanıcı", "kullanici", "rapor", "dashboard",
    "menü", "menu", "modül", "modul", "ayar", "nasıl", "nasil",
    "nerede", "hangi", "ekle", "oluştur", "olustur", "sil", "düzenle",
    "yetki", "erişim", "erisim", "purchase", "inventory", "accounting",
    "payroll", "project", "proje", "bordro", "ik", "pos",
    "fiyat", "indirim", "onay", "onayla", "akış", "workflow",
    "adım", "adim", "nasıl", "nasil", "yapılır", "yapilir",
})

INTENT_GREETING = "greeting"
INTENT_ODOO = "odoo_question"
INTENT_UNCLEAR = "unclear"


def detect_intent(message: str) -> str:
    text = (message or "").lower().strip()
    words = text.split()

    if any(kw in text for kw in _ODOO_KEYWORDS):
        return INTENT_ODOO

    if "?" in text and len(words) > 4:
        return INTENT_ODOO

    if any(kw in text for kw in _GREETING_KEYWORDS):
        return INTENT_GREETING

    if len(words) <= 5:
        return INTENT_UNCLEAR

    # Longer messages with no clear Odoo keyword default to Odoo (benefit of doubt)
    return INTENT_ODOO
