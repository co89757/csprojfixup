# C# Project mangling toolset 
## Prerequisites:
- Install python2 and pip (package management tool)
- install `lxml` package 
```sh
$pip install lxml 
```
- Drop the 3rdparty/xml.exe under your $(GitRoot)/usr/bin/
- open git-bash and go 
```sh
$ python projfixup.py --help
```
start from there!

## Optional XML formatting tool:
It also contains a XML formatter tool `prettify_xml.sh` that uses `xmlstarlet` to do the xml formatting for all the .csproj files under current directory (recursive).
You need make sure `xmlstarlet` is in your PATH. For windows, simply drop the xml.exe into your $(GitRoot)/usr/bin/ 

and a sample run looks like (in Git-bash)
```sh
$ sh prettify_xml.sh
```