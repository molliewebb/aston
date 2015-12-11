# Installation #

## Windows ##

You may need run the installer "as administrator" for it to work.

# Manually Building Aston #

Aston is written using cross-platform technologies, so it can run on a variety of different platforms. If the prebuilt binaries aren't working on your computer, it may be possible to get Aston to run by manually installing its dependencies.

## Windows ##

Download [Python 2.7](http://www.python.org/ftp/python/2.7.2/python-2.7.2.msi), [Numpy](http://sourceforge.net/projects/numpy/files/NumPy/1.6.1/numpy-1.6.1-win32-superpack-python2.7.exe/download), [Scipy](http://sourceforge.net/projects/scipy/files/scipy/0.9.0/scipy-0.9.0-win32-superpack-python2.7.exe/download), [Matplotlib](http://sourceforge.net/projects/matplotlib/files/matplotlib/matplotlib-1.1.0/matplotlib-1.1.0.win32-py2.7.exe/download), and [PyQt](http://www.riverbankcomputing.co.uk/static/Downloads/PyQt4/PyQt-Py2.7-x86-gpl-4.8.6-1.exe) from their respective websites and install them. Also, download the source code for Aston from the Downloads section.

You should then be able to open the aston.py file in the main directory with the pythonw.exe program.

_With some versions of Windows, you may need the [Visual C++ libraries](http://www.microsoft.com/en-us/download/details.aspx?id=29) before Aston will start (Windows may give an error like "This application has failed to start because the application configuration is incorrect. Reinstalling the application may fix the problem" if this is the case.)_

## Mac OS X ##

`PyQt` isn't precompiled for Mac OS X, so the fastest and most reliable way to get Aston running is by installing the dependencies through `MacPorts`.
Download the dmg file for your version of Mac OS [here](http://www.macports.org/install.php) and install it.
Now, in the terminal type:
```
sudo ports install python27
sudo ports install py27-numpy
sudo ports install py27-scipy
sudo ports install py27-matplotlib
sudo ports install py27-pyqt
```

Download the Aston source code and decompress it.
You should now be able to launch Aston through the command line by being in the main directory and typing:
```
python27 aston.py
```

# Linux #

### Ubuntu ###

### Arch Linux ###
Download the Aston source code and then type in the terminal:
```
sudo pacman -S python2-numpy python2-scipy python2-matplotlib python2-pyqt
```
You should now be able to run Aston by being in its main directory and typing:
```
python2 aston.py
```

## Source ##
In addition to the extra libraries, to use the source distribution you need to generate `*.PNG` files from the `*.SVG` files in the /aston/ui/icons/ directory. Also, you may want to "Release" any `*.TS` translation files in /aston/i18n/ into their corresponding `*.QM` files using Qt Linguist if you need language localizations.