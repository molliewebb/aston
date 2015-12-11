# Introduction #

Aston is a cross-platform, open source program for the analysis of chromatographic data. It's named for Francis William Aston, creator of the first fully functional mass spectrometer, and written using Python, Numpy, Scipy, Matplotlib and `PyQt`.

# Features #

  * Native support for several Agilent Chemstation, Agilent Masshunter and Thermo Isodat file formats
  * Several graphical display options for visualizing data
  * Tabular interface to chromatographic file information
  * Simple integration and carbon isotope calculation features

# Version 0.6.2 Out! #

In addition to new features for 0.6, preliminary support for Inficon HPS files has been added in.

New features for 0.6 include:

  * Major speed improvements.
  * Peaks can be integrated "periodically" (e.g. if FIA isn't recognized in the file, this should still split peaks at the appropriate places).
  * Multiprocessing support (in integration) can be enabled/disabled in settings.
  * (Very) simple spectral matching against AMDIS libraries and preliminary support for compound libraries. This may still be fairly buggy.
  * Several bug-fixes and user interface improvements.

NOTE: There is a bug in this version (and all previous versions) where Agilent MS traces with high abundance ions (above 16384 counts) will be read at lower intensities than they are. It will be fixed in the next version.

![http://wiki.aston.googlecode.com/git/aston-demo.png](http://wiki.aston.googlecode.com/git/aston-demo.png)