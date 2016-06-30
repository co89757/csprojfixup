#!/usr/bin/python
# -*- coding: utf-8 -*-
# 
#### NOTE: 3rd party dependency: lxml 
#### Install it using pip: open your python prompt > pip install lxml 
#### and run the script in the $(INETROOT) > python projfixup.py --help  
import os
import os.path as path
import re
from lxml import etree as et 
import fnmatch
import sys
import json 
import logging 
from optparse import OptionParser, OptionGroup  

LOG_FORMAT="%(asctime)s [%(levelname)s]<%(funcName)s>: %(message)s"
logging.basicConfig(format=LOG_FORMAT, level = logging.DEBUG, filename = "csprojfix.log" )
# from itertools import imap 
def find_all_files_recur(rootdir, pattern):
    """find all files matching given pattern recursively under root

    :rootdir: toplevel directory
    :pattern: glob pattern 
    :returns: list of matching files 

    """
    files = []
    for dirpath, dirnames, filenames in os.walk(rootdir):
        matches = fnmatch.filter(filenames, pattern)
        files.extend(map(lambda fn: path.join(dirpath,fn),matches) )
    return files

def find_all_files_recur_iter(rootdir, globpattern):
    """iterator to all files of given glob pattern 
    
    return a iterator to all files of given pattern under given directory
    
    Arguments:
        rootdir {path-string} -- root directory
        globpattern {string} -- pattern (not regex)
    
    Yields:
        [type] -- [description]
    """
    for dirpath,dirnames,filenames in os.walk(rootdir):
        for filename in filenames:
            if fnmatch.fnmatch(filename,globpattern):
                yield path.join(dirpath,filename)

## UNUSED
def qualified(tagname, ns):
    "convert a tag name to its qualified name compliant with lxml-friendly form {ns}<tagname>"
    return "{%s}tagname" % ns 

class XmlFile(object):
    """a wrapper for xml processing over lxml elementTree, refer to http://lxml.de/tutorial.html for details """
    def __init__(self,filename):
        self.filename = filename 
        self.handle = open(filename, 'r+')
        self.tree = et.parse(self.handle)
        self.ns=self.tree.getroot().nsmap.get(None)
    @property 
    def nsmap(self):
        return self.tree.getroot().nsmap


    @property  
    def namespace(self):
        return self.ns 
    def xpath(self,xpath):
        return self.tree.xpath(xpath)
    def find_first(self,elempath):
        return self.tree.find(elempath)
    def finditer(self,elempath):
        return self.tree.iterfind(elempath)
    def write2(self,file):
        with open(file, 'w+') as of:
            of.write(et.tostring(self.tree.getroot(), pretty_print=True))

    def write(self,file):
        self.tree.write(file, pretty_print = True, encoding="utf-8", xml_declaration=True)
    def overwrite(self):
        self.write(self.filename)
    def iter_descendents(self, tag = None, *tags):
        return self.tree.iter(tag,*tags)
    def find_tag_and_replace_text(self,tag, text):
        e = self.find_first(".//{*}%s" % tag)
        if e is not None:
            e.text = text 
        else:
            print "[WARNING] element %s not found" % tag 
    def find_elements_and_apply(self,elempath, action):
        "find all elements by xpath and apply action to them"
        for elem in self.finditer(elempath):
            action(elem)

    def append_to_first(self,root_xpath, xmlstring):
        """deserialize a xml-string to xmlElement and 
        append it to the first root found by the xpath expression
        
        Arguments:
            root_xpath {[Xpath expression]} -- [Xpath to the root]
            xmlstring {[string]} -- [XML string of the child node]

        """
        root = self.find_first(root_xpath)
        if root is None:  
            raise ValueError("the parent node to which the new node appends to is not existent")
        child = et.fromstring(xmlstring)
        root.append(child) 
    def add_next_to(self, node_xpath, xmlstring):
        """add a element next to give node by its xpath 
        
        similar to append_to_first(), this works on adding sibling 
        
        Arguments:
            node_xpath {string} -- xpath expression
            xmlstring {string} -- xml string for the added node
        """ 
        brother = self.find_first(node_xpath)
        if brother is not None:
            newbrother = et.fromstring(xmlstring)
            brother.addnext(newbrother)


    def __enter__(self):
        return self 
    def __exit__(self,exc_type, exc_val, exc_tb):
        if not self.handle.closed:
            self.handle.close()
        


def find_all_hintpaths(filename):
    "get a dict of reference -> hint paths in csproj file"
    ref2path = {}
    with XmlFile(filename) as proj:
        for elem in proj.finditer(".//{*}HintPath"):
            elem_ref = elem.getparent()
            ref = elem_ref.get("Include")
            path = elem.text 
            ref2path[ref] = path 
            
    return ref2path 

## helper 
def aggregate_references_to_path_lookup(rootdir='.', jsondumpfile = "references.json"):
    pat = "*.csproj"
    references = { }
    for fname in find_all_files_recur_iter(rootdir,pat):
        logging.debug( "Found project file:[%s]" , fname )
        references.update(find_all_hintpaths(fname))

    ## dump the dictionary to a json file 
    jsonstr = json.dumps(references, sort_keys = True, indent = 2, separators=(',', ': '))
    with open(jsondumpfile, "w+") as dumpf:
        dumpf.write(jsonstr)
        print "Dumped <ref:hintpath> mapping to JSON file: %s" % jsondumpfile

def is_same_reference(name1, name2):
    "compare if two references are the same, ignore version and other meta info" 
    return name1.split(',')[0].strip() == name2.split(',')[0].strip()

def replace_all_hint_paths_from_file(rootdir='.', jsonfile="references.json"):
    """replace the HintPath element text in all csproj files according the the lookup in jsonfile 
    Keyword Arguments:
        rootdir {str} -- [root directory] (default: {'.'})
        jsonfile {str} -- [json file for ref->path lookup] (default: {"references.json"})
    """
    ## parse json file to a dict 
    if not os.path.exists(jsonfile) :
        print "[ERROR] reference remap json file: %s not found!" % jsonfile
        return -1
    lookup = {}
    try:
        with open(jsonfile,'r+') as jsonf:
            lookup = json.load(jsonf) 
    except Exception:
        raise ValueError("%s is not well-formatted JSON, check for unquoted keys or extra trailing commas" % jsonfile)

    logging.debug("reference-lookup populated, there are a total of %d entries", len(lookup) )
    for proj in find_all_files_recur_iter(rootdir,"*.csproj"):
        with XmlFile(proj) as xml:
            for path in xml.finditer(".//{*}HintPath"):
                refname = path.getparent().get("Include")
                new_path = lookup.get(refname)
                if new_path:
                    path.text = new_path
                else:
                    logging.debug("reference key: %s is not found in the lookup, skipping...", refname)

            ## overwrite it 
            xml.overwrite()



            

    


def add_CLS_compliance_property(csprojfile):
    """
    add AssemblyClsCompliant property to the csproj file 
    to avoid non-CLS compliant error from quickbuild
    """  
    cls_node = """
    <PropertyGroup>
        <AssemblyClsCompliant>False</AssemblyClsCompliant>
    </PropertyGroup>
    """
    with XmlFile(csprojfile) as proj:
        if proj.find_first(".//{*}AssemblyClsCompliant") is None:
            proj.add_next_to(".//{*}PropertyGroup", cls_node)
            proj.overwrite()
            logging.debug("adding CLS-compliance element to [%s]", csprojfile )
        else:
            logging.debug("<AssemblyClsCompliant> already exists in file [%s]" , csprojfile )


def add_CLS_compliance_property_to_all(rootdir='.'):    
    for projfile in find_all_files_recur_iter(rootdir, "*.csproj"):
        add_CLS_compliance_property(projfile)
    print "[INFO] Fixed CLS-Compliance property" 



def fix_vs_unittest_framework_reference(csprojfile):
    Include = "Microsoft.VisualStudio.QualityTools.UnitTestFramework"
    xpath_expr = ".//{*}Reference[@Include='%s']" % Include
    hintpath_node = et.Element("HintPath")
    hintpath_node.text = "$(PkgVisualStudio_UnitTest_Corext)\\lib\\net40\\Microsoft.VisualStudio.QualityTools.UnitTestFramework.dll"

    with XmlFile(csprojfile) as proj:
        refnode = proj.find_first(xpath_expr)
        if refnode is not None and refnode.find(".//{*}HintPath") is None:
            refnode.append(hintpath_node)
            logging.debug( "added VS UnitTest reference for : [%s]" , csprojfile)
        elif refnode is not None and refnode.find(".//{*}HintPath") is not None:
            refnode.find(".//{*}HintPath").text = hintpath_node.text
            logging.debug( "updated VS unittest reference for [%s]" , csprojfile)
        else:
            logging.debug( "VS UnitTest reference is not found in [%s]" , csprojfile)

        proj.overwrite() 

def fix_all_unittest_reference(start_dir = '.'):
    """Fixing the hintpaths to Microsoft UnitTest Framework 
    for all .csproj files recursively under start_dir 
    
    Keyword Arguments:
        start_dir {str} -- [startding root directory] (default: {'.'})
    """
    for fn in find_all_files_recur_iter(start_dir,"*.csproj"):
         fix_vs_unittest_framework_reference(fn)
    print "[INFO] Fixed HintPath to MS Unittest frameworks"




def update_paths_in_reference_lookup(ref_json_file, outfile = None):
    "batch update the hint-paths of the references"
    pathpattern = re.compile(r"^(?:.*\\packages\\\S+)(\\lib\\.*\.dll)")
    if not os.path.exists(ref_json_file):
        print "references file %s does not exist. quitting..." % ref_json_file 
        return
    refdict = {}
    outrefdict = {} ## only store the references outside of External\ folder 
    with open(ref_json_file,'r+') as f:
        refdict = json.load(f) 
    for k,v in refdict.iteritems():
        package_name = k.split(",")[0].strip()
        logging.debug("get package name: [%s]", package_name)
        if pathpattern.match(v):
             mangled_pkg_name = package_name.replace(".","_")
             repl = "$(Pkg%s)" % mangled_pkg_name  
             new_v=pathpattern.sub(r"%s\1" % repl , v) 
             logging.debug("New path is [%s]", new_v )
             outrefdict[k] = new_v
        else:
            logging.debug("Pattern match is not found for path: %s", v) 


    #make new json 
    if outfile:
        with open(outfile,"w+") as of:
            json.dump(outrefdict, of, indent = 2, separators=(',',': ' )) 
    else:
        with open(ref_json_file, 'w+') as of :
            json.dump(outrefdict,of,indent = 2, separators=(',',': ' ))





def convert_references_to_versionless(csprojfile, exclude_external = True):
    """convert all assembly references to version-agnostic ones
    
    For example: 
     <Reference Include="Microsoft.WindowsAzure.Configuration, Version=3.0.0.0, Culture=neutral, PublicKeyToken=31bf3856ad364e35, processorArchitecture=MSIL">
     turning to 
     <Reference Include="Microsoft.WindowsAzure.Configuration/> 
    
    Arguments:
        csprojfile {[str]} -- [path to .csproj file ]   
        exclude_external {[boolean]} -- [True to exclude references in External\ folder]
    """

    assert os.path.exists(csprojfile) 
    logging.info("** Peeling Version ** File <%s>", csprojfile)
    with XmlFile(csprojfile) as xml:
        for node in xml.finditer(".//{*}Reference[@Include]"):
            ref_name = node.get("Include")
            is_in_external =  ( (node.find("./{*}HintPath") is not None) and 'External' in node.find("./{*}HintPath").text ) 
            has_version = ( 'Version' in ref_name )
            trimmable = False 

            if exclude_external:
                if has_version and (not is_in_external) :
                    trimmable = True
            else:
                trimmable = has_version  



            if trimmable:
                logging.debug("ReferenceName BEFORE: %s" , ref_name)
                trimed_name = ref_name.split(',')[0] 
                logging.debug("ReferenceName AFTER: %s", trimed_name) 
                node.set('Include', trimed_name) 
        xml.overwrite() 
    logging.info("** DONE ** ")


def peel_version_off_references_for_all(rootdir, exclude_external = True):
    for csfile in find_all_files_recur_iter(rootdir,"*.csproj"):
        convert_references_to_versionless(csfile, exclude_external) 


def add_qtest_properties(testprojfile):
     qtesttypenode = """
     <QTestType>MsTest_Latest</QTestType>
     """
     qtestdirnode = "<QTestDirToDeploy>$(OutDir)</QTestDirToDeploy>"
     with XmlFile(testprojfile) as test: 
        if test.find_first(".//{*}QTestType") is None :
            test.append_to_first(".//{*}PropertyGroup", qtesttypenode ) 
            test.append_to_first(".//{*}PropertyGroup" , qtestdirnode) 
            test.overwrite()  
        else: 
            logging.debug( "%s already has QTest properties, doing nothing and quitting" , testprojfile) 
            

def add_qtest_properties_to_all(rootdir):
    for test in find_all_files_recur_iter(rootdir, "*[tT]est*.csproj"):
        add_qtest_properties(test) 

def update_dotnet_version(csprojfile, newversion):
    "update .NET framework target version property in .csproj"
    if re.match(r"v[0-9.]+", newversion) is None: 
        raise ValueError("Invalid version string, should be like v4.5[.2]") 
    with XmlFile(csprojfile) as prj: 
        prj.find_tag_and_replace_text("TargetFrameworkVersion",newversion) 
        prj.overwrite()

def update_dotnet_version_all(rootdir, newversion):
     for proj in find_all_files_recur_iter(rootdir,"*.csproj"):
         update_dotnet_version(proj, newversion) 





def main():
    usage="""
    Usage: %prog [<global-options>] <action> [<action-options>]
    where <global-options> are:
    -r|--root       - starting root directory to look for the .csproj files, by default ./ 
    -h | --help     - see help manual 
    <action> is one of:
    cls             - add CLS-compliance property if not alrady exist 
    qtest           - add QTest related properties to all Test projects 
    unittest        - fix paths to Microsoft.VisualStudio.QualityTools.UnitTestFramework  
    dotnetver       - update .NET framework target version to given version  
    versionless     - make references versionless so they are not locked to any partiuclar version 
    pathfix         - replace all the HintPath text to correct corext pacakge path according to the provided mapping in a json file
    initlookup      - generate the current reference-to-hintpath JSON file "refs_old.json", you can update the values to the correct paths before you do pathfix
    Example: %prog --root "path/to/repo" cls  - fixes all CLS-properties under repo root  
    """
    
    parser = OptionParser(usage=usage) 
    pathfixopt = OptionGroup(parser,"HintPath Fxiup Options", "Options only for <pathfix> action, for example to specify path mapping file")
    parser.add_option('-r','--root', dest = "rootdir", help = "set rootdir, usually it's your repo rootdir", default=".")
    pathfixopt.add_option('-m','--map',dest='lookupfile',help="specify reference path mapping JSON file") 
    parser.add_option_group(pathfixopt) 
    donetver_opt = OptionGroup(parser,"DotNet Framework Reversion Options", "Options for <dotnetver> action, i.e. specify version to update to")
    donetver_opt.add_option("-v","--version", dest = 'newversion', help="specify new version for TargetFrameworkVersion property, such as v4.5.2")
    parser.add_option_group(donetver_opt)
    versionless_opt = OptionGroup(parser, "Options for action <versionless>", "Flags to include/exclude binaries under External folder when peeling package-version info" )
    versionless_opt.add_option('--include-external', action='store_true', dest='include_external', help="Flag to include version-peeling for binaries under External folder", default=False)
    parser.add_option_group(versionless_opt)
    (options, args) = parser.parse_args() 


    rootdir = options.rootdir 
    lookupfile = options.lookupfile
    if len(args) != 1:
        parser.error("Must specify one <action>, choose from <cls | unittest | dotnetver | qtest | versionless | pathfix | initlookup> ") 
    action = args[0] 
    if action == 'cls':
        add_CLS_compliance_property_to_all(rootdir)
    elif action == "unittest": 
        fix_all_unittest_reference(rootdir) 
    elif action == "versionless": 

        peel_version_off_references_for_all(rootdir, not options.include_external) 
    elif action == 'pathfix':  
        if not lookupfile:
            parser.error("Must specify --map LOOKUPFILE for the remapped reference->hintpath JSON file\n" 
                "for example --map path/to/remapped_refs.json")
        replace_all_hint_paths_from_file(rootdir, lookupfile) 
    elif action == 'initlookup': 
        aggregate_references_to_path_lookup(rootdir,"refs_old.json")
    elif action == "qtest": 
        add_qtest_properties_to_all(rootdir)  
    elif action == 'dotnetver': 
        if options.newversion is None: 
            parser.error("must specify new version for target .NET framework")
        update_dotnet_version_all(rootdir, options.newversion)  
    else: 
        parser.error("invalid action! please refer to -h manual for valid actions")

        










if __name__ == '__main__':
    main()
    # rootdir = "." ## your $(INETROOT) here
    # rootdir = "E:\\repos\\geospatial\\IncrementalGridStore\\" ## your $(INETROOT) here
    # reference_json_file = "E:\\repos\\geospatial\\IncrementalGridStore\\references.json" ## your $(inetroot)\references.json 
    # # aggregate_references_to_path_lookup(rootdir)
    # lookupfile = "C:\\Users\\colinli\\experiment\\scripts\\xml\\refs_remap.json"
    # replace_all_hint_paths_from_file(rootdir, lookupfile)
    # peel_version_off_references_for_all(rootdir)
    # aggregate_references_to_path_lookup(rootdir,"refs2.json")
    