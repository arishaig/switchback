# Maintainer: Your Name <your.email@example.com>

pkgname=switchback
pkgver=1.0.0
pkgrel=1
pkgdesc="Solar-based dynamic wallpaper switcher for hyprpaper"
arch=('any')
url="https://github.com/yourusername/switchback"
license=('MIT')
depends=(
    'python>=3.10'
    'python-astral'
    'python-yaml'
    'python-pytz'
    'hyprpaper'
)
makedepends=(
    'python-setuptools'
    'python-build'
    'python-installer'
    'python-wheel'
)
source=("${pkgname}-${pkgver}.tar.gz")
sha256sums=('SKIP')  # Update with actual checksum

build() {
    cd "$srcdir/$pkgname-$pkgver"
    python -m build --wheel --no-isolation
}

package() {
    cd "$srcdir/$pkgname-$pkgver"

    # Install Python package
    python -m installer --destdir="$pkgdir" dist/*.whl

    # Install systemd service
    install -Dm644 switchback.service \
        "$pkgdir/usr/lib/systemd/user/switchback.service"

    # Install example config
    install -Dm644 config.yaml \
        "$pkgdir/usr/share/switchback/config.yaml.example"

    # Install README
    install -Dm644 README.md \
        "$pkgdir/usr/share/doc/$pkgname/README.md"
}
