import os
import subprocess
import xml.etree.ElementTree as ET

pkgName = 'plugin.image.ShotwellViewer'
tree = ET.parse(pkgName + "/addon.xml")
root = tree.getroot()

def combine_list(l, sep = " "):
    result = ""
    for i in l:
        result += str(i) + sep
    return result

def getGitFileList(directory=""):
    result = []
    output = subprocess.check_output("git ls-files " + str(directory), shell=True)
    for f in output.split('\n'):
        if f!='':
            result += [f]
    return result

if root.tag == "addon":
    version = root.attrib["version"]
    zipName = "releases/" + pkgName + "-" + str(version) + ".zip"
    os.system("rm -f " + zipName)
    required_files = combine_list(getGitFileList(pkgName))
    createZip = "zip " + zipName + " " + required_files
    os.system(createZip)
    os.system("git add " + zipName)
    
