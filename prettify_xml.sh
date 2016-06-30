### Dependency: xmlstarlet http://xmlstar.sourceforge.net/doc/UG/xmlstarlet-ug.html 
### Download the binary xml.exe and put it inside $(GitHome)/usr/bin/


ROOT=$(pwd)
GLOB="*.csproj"
### "bash strict mode" quit on any non-zero exit status early  
## see http://redsymbol.net/articles/unofficial-bash-strict-mode/ 
set -euo pipefail
trap "echo 'error: Script failed: see failed command above'" ERR
export PS4='+(${BASH_SOURCE}:${LINENO}): ${FUNCNAME[0]:+${FUNCNAME[0]}(): }'

### Color output setup ###
END="\e[0m"
RED="\e[0;31m"
GREEN="\e[0;32m"
YELLOW="\e[0;33m"
BLUE="\e[0;34m"

## prettify xml in place 
pretty_xml()
{
    if [[ $# -ne 1 ]]; then
        echo "Usage: pretty_xml <xmlfile>"
        exit -1 
    fi
    TMP_XML=$(mktemp)
    xml fo -s 2 "$1" > "${TMP_XML}" 
    mv "${TMP_XML}" "$1" 
}

## reformat all .csproj files recursively
prettify_all_csprojs_recursive()
{
    local rootdir="."
    local glob="*.csproj"
    if [[ $# -eq 2 ]]; then
        rootdir=$1 
        glob="$2"
        echo "setting starting directory to $1, pattern $2"
    fi
    echo "root: $rootdir  glob:  $glob"
     find $rootdir -name "$glob" -type f| while read fname; do
        echo -e "formatting ${GREEN} $fname ${END} \n"
        pretty_xml ${fname}
    done 
     
}

prettify_all_csprojs_recursive
