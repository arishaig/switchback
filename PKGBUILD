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
    'python-pillow'
    'hyprpaper'
)
optdepends=(
    'python-gobject: for GUI configuration tool'
    'gtk4: for GUI configuration tool'
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
    /usr/bin/python -m build --wheel --no-isolation
}

package() {
    cd "$srcdir/$pkgname-$pkgver"

    # Install Python package
    /usr/bin/python -m installer --destdir="$pkgdir" dist/*.whl

    # Install systemd service
    install -Dm644 switchback.service \
        "$pkgdir/usr/lib/systemd/user/switchback.service"

    # Install desktop file
    install -Dm644 switchback-gui.desktop \
        "$pkgdir/usr/share/applications/switchback-gui.desktop"

    # Install example config
    install -Dm644 config.yaml \
        "$pkgdir/usr/share/switchback/config.yaml.example"

    # Install README
    install -Dm644 README.md \
        "$pkgdir/usr/share/doc/$pkgname/README.md"
}
