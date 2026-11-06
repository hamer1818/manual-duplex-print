"""Testler gerçek ayarlara, önbelleğe ve yazıcıya dokunmaz: her çalıştırma geçici klasör kullanır,
CUPS'a giden çağrılar sahte işlevlerle değiştirilir. Çalıştırma: ./test.sh"""
import os
import tempfile

_KOK = tempfile.mkdtemp(prefix="yazdir-test-")
os.environ["XDG_CACHE_HOME"] = os.path.join(_KOK, "cache")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_KOK, "config")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LANGUAGE"] = "tr"
