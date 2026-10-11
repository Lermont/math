"""Public runtime names plus explicitly synthetic, reproducible test corpora."""
import random
import sys


def corpora(seed=1282026):
    rng = random.Random(seed)

    def windows(n, size, stride=1, alphabet=bytes(range(256))):
        source = bytes(rng.choices(alphabet, k=size+(n-1)*stride))
        values = [source[i*stride:i*stride+size] for i in range(n)]
        rng.shuffle(values)
        return values

    def urls(n):
        values = [f"/catalog/{['brakes','engine','tools','wheels'][i%4]}/{i:06d}".encode()
                  for i in range(n)]
        rng.shuffle(values)
        return values

    positive = windows(128, 64)
    text = windows(96, 48, 2, b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    identifiers = [rng.randbytes(8).hex().encode() for _ in range(128)]
    labels = [f"Заказ {i:04d}: {['новый','оплачен','доставлен','отменён'][i%4]}".encode()
              for i in range(64)]
    rng.shuffle(labels)
    periodic = [(b"abracadabra" * 12)[i%11:i%11+40+i%31] for i in range(64)]
    rng.shuffle(periodic)
    repeated = [f"customer/{i:04d}/active".encode() for i in range(32)] * 4
    rng.shuffle(repeated)
    return [
        dict(id="overlap_binary_128", title="Перекрывающиеся байтовые фрагменты", kind="synthetic",
             description="128 окон по 64 байта, сдвиг 1; общий случайный источник 191 байт; порядок перемешан.",
             strings=positive),
        dict(id="overlap_text_96", title="Перекрывающиеся текстовые фрагменты", kind="synthetic",
             description="96 окон по 48 байт, сдвиг 2; алфавит ASCII из 62 символов; порядок перемешан.", strings=text),
        dict(id="urls_32", title="URL: 32 строки", kind="synthetic",
             description="Пути каталога с общими префиксами; уникальные товары; порядок перемешан.", strings=urls(32)),
        dict(id="urls_128", title="URL: 128 строк", kind="synthetic",
             description="Тот же шаблон путей каталога, 128 товаров.", strings=urls(128)),
        dict(id="python_modules", title="Названия модулей Python", kind="runtime_public_names",
             description="Все имена из sys.stdlib_module_names данного Python; публичные названия, без содержимого файлов.",
             strings=[s.encode() for s in sorted(sys.stdlib_module_names)]),
        dict(id="random_ids_128", title="Случайные идентификаторы", kind="synthetic",
             description="128 независимых 16-символьных шестнадцатеричных ID; отрицательный контроль.", strings=identifiers),
        dict(id="utf8_labels_64", title="Подписи на русском UTF-8", kind="synthetic",
             description="Номера и четыре статуса заказа; все 64 подписи различны.", strings=labels),
        dict(id="periodic_64", title="Периодические строки", kind="synthetic",
             description="64 фрагмента повторения abracadabra, длины 40–70; часть строк содержится в других.", strings=periodic),
        dict(id="duplicates_128", title="Повторяющиеся строки", kind="synthetic",
             description="32 уникальные строки, каждая повторена четыре раза; порядок перемешан.", strings=repeated),
        dict(id="overlap_binary_1024", title="Перекрытия: 1 024 строки", kind="synthetic",
             description="Проверка роста: 1 024 окна по 64 байта, сдвиг 1, порядок перемешан.", strings=windows(1024, 64)),
        dict(id="urls_16384", title="URL: 16 384 строки", kind="synthetic",
             description="Проверка роста: 16 384 пути каталога по тому же шаблону.", strings=urls(16384)),
    ]
