# Maintainer: Ashutosh Tiwari <ashutosh@ashutoshtiwari.dev>

pkgname=plasmoji-git
pkgver=b526963
pkgrel=1
pkgdesc="A Wayland-native emoji, kaomoji, and GIF selector for KDE Plasma 6"
arch=('any')
url="https://github.com/iashutoshtiwari/plasmoji"
license=('MIT')
depends=('python' 'pyside6' 'wl-clipboard' 'wtype')
makedepends=('git' 'python-setuptools' 'python-build' 'python-installer' 'python-wheel')
provides=('plasmoji')
conflicts=('plasmoji')
source=("git+https://github.com/iashutoshtiwari/plasmoji.git")
sha256sums=('SKIP')

pkgver() {
  cd "$srcdir/plasmoji"
  git describe --long --tags --always | sed 's/\([^-]*-g\)/r\1/;s/-/./g'
}

build() {
  cd "$srcdir/plasmoji"
  python -m build --wheel --no-isolation
}

package() {
  cd "$srcdir/plasmoji"

  # 1. Install the Python module using the standard installer into python site-packages
  python -m installer --destdir="$pkgdir" dist/*.whl

  # 2. Although python-installer creates the executable in /usr/bin/plasmoji (from pyproject.toml),
  # we ensure it has proper permissions just in case.
  chmod 755 "$pkgdir/usr/bin/plasmoji"

  # 3. Install systemd user service
  install -Dm644 assets/plasmoji.service "$pkgdir/usr/lib/systemd/user/plasmoji.service"

  # 4. Modify the systemd service to use the absolute path /usr/bin/plasmoji instead of generic module calls
  # python -m plasmoji is fine, but since we have a console script, we can point it to /usr/bin/plasmoji.
  sed -i 's|ExecStart=.*|ExecStart=/usr/bin/plasmoji|' "$pkgdir/usr/lib/systemd/user/plasmoji.service"

  # 5. QML directory needs to be globally accessible if packaged via site-packages
  # By default the pip install places qml/ parallel if included in wheel, but
  # for safety we install the QML explicitly to the module directory if wheel misses it.
  local site_packages=$(python -c "import site; print(site.getsitepackages()[0])")
  install -Dm644 qml/main.qml "$pkgdir$site_packages/plasmoji/main.qml"
}
