Name:           rhythm-linux
Version:        1.0.0
Release:        1%{?dist}
Summary:        A native Linux music library and player
License:        MIT
URL:            https://github.com/keanehatescoding/rhythm-linux
Source0:        %{url}/archive/v%{version}.tar.gz#/%{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros

Requires:       python3-gobject
Requires:       python3-mutagen >= 1.45
Requires:       gtk4
Requires:       gstreamer1-plugins-base
Requires:       gstreamer1-plugins-good
Requires:       gstreamer1-plugins-ugly-free
Requires:       gstreamer1-libav
Recommends:     ifuse
Recommends:     libimobiledevice-utils
Recommends:     kde-connect

%description
Rhythm (Linux) is a local music player for GTK 4. It scans a music folder for
MP3, AAC/M4A, FLAC, WAV, ALAC and AIFF files, with gapless playback, crossfade,
an equaliser, ratings, play counts and M3U playlists.

It also has a read-only view of a connected iPhone (through ifuse and
libimobiledevice) and can send tracks to a paired phone with KDE Connect.

Not affiliated with Apple.

%prep
%autosetup -p1

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files rhythm_linux
install -Dm644 data/rhythm-linux.desktop \
  %{buildroot}%{_datadir}/applications/rhythm-linux.desktop

%files -f %{pyproject_files}
%{_bindir}/rhythm-linux
%{_datadir}/applications/rhythm-linux.desktop

%changelog
* Thu Nov 05 2026 Rhythm (Linux) authors <catherine.kiplagat20@gmail.com> - 1.0.0-1
- Initial release.
