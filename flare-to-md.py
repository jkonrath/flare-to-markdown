#!/usr/bin/env python3

import yaml
import os
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET
import textwrap
import re
import sys
from distutils.dir_util import copy_tree

def main():
    """
    Converts a Flare clean XHTML output to markdown, suitable for Jekyll.
    
    Jon Konrath (jkonrath@rumored.com)

    You need to do this one-time install:
        python -m pip install pyyaml
    If you're not sure you have these installed:
        python -m pip list

    This assumes you're in a docs-src directory that has a very specific topic.yml file for TOC that you probably don't have.
    This goes through the src/_data/topic.yml and finds any items with flare: true flag set.
    """
    print("Running flare-to-md with Python "+sys.version)
    # iterate through the src/data/topic.yml file
    with open('src/_data/topic.yml') as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
        for book in data:
            bookname = book["link"]
            if "flare" in book:
                print("    "+bookname+" is a Flare book.")
                if book["flare"]: # you *could* set flare: false
                    convertbook(bookname);
                    print("    "+bookname+" conversion finished.")
    print("Flare to MD conversion finished.")

def convertbook(bookname):
    print("    converting "+bookname)

    # Recursively copy everything in src/_topic dir to src/topic.
#TODO: (check if src/_topic really contains raw xhtml output and isn't a dir in a dir, etc)
#TODO: at bare minimum, it needs an index.html in the root

    #old way:
    #if the destination dir already exists, delete it
    #TODO: shutil.copytree doesn't clobber files, so I have to delete the old dir first.
    # There's a performance hit because you have to re-copy everything each run, so rethink this later?
    # if os.path.isdir("src/"+bookname):
    #     shutil.rmtree("src/"+bookname)
    # try:
    #     shutil.copytree("src/_"+bookname,"src/"+bookname) #these paths are probably kludgy
    # except shutil.Error as e:
    #     print('Directory not copied. Error: %s' % e)
    # except OSError as e:
    #     print('Directory not copied. Error: %s' % e)

    #new way: no delete needed. This will leave behind unused files, though.
    copy_tree("src/_"+bookname,"src/"+bookname)

    #  For each file recursively in the whole dirtree:
    for dirname, subdirname, filelist in os.walk("src/"+bookname):
        for fname in filelist:

            if fname.endswith(".html"):  # or .htm? or both?
                # You parse the .html, but write the .md, then delete the .html
                p = Path(dirname)
                htmlfname = p / fname
                mdfname = htmlfname.with_suffix('.md')
                print(htmlfname)

# TODO: check that the name isn't weird: spaces, trademark symbols, whatever

                root = ET.parse(htmlfname).getroot()

                # Getting Stuff For The YAML
# TODO: only title is really required. The others I think may be in the head, so look there and skip if missing
                # - get <title>, clean it up, and make it the pageTitle
                pageTitle = cleanelement(root.find('head/title'))
                # - get the first p contents, clean it up, and make it the description.
                description = cleanelement(root.find('body/p'))
                #TODO: both of these could fail because of missing elements
                #TODO: no navtitle - bw doesn't do anything, though. I hope we don't get any crazy TOC titles out of this
                #TODO: someday figure out keywords

                # extract everything within <body> (excluding the <body></body> tags)
                # This will be a long string with a bunch of elements, hopefully starting with a <h1>
                # Also has whatever line breaks the Flare source had.
                bod = root.find('body')
                innerbody = ""
                for child in bod:
                    innerbody += ET.tostring(child).decode("utf-8")#.replace("\\r\\n", "\\n")


                #make array of original file, split by newlines, has spaces and nested garbage
                srcbodyarray = innerbody.split('\n')

                # make flatbody one giant line with no spaces
                flatbody = ""
                for line in srcbodyarray:
                    flatbody += line.strip()


                # add a \n before and after each open and close tag.
                flatbody = re.sub("(<[^>]*>)",r"\n\1\n",flatbody)
                flatbody = re.sub("\n\n",r"\n",flatbody)

                # make an array that splits the above by \n. note that this has blank lines.
                flatbodyarray = flatbody.split('\n')

                # Here are the cases handled in the conversion:
                # 0. Void tags (<br/>, <img * />, etc) are passed through.
                # 1. <h1>-<h4> become "# " - "#### "
                # 2. <p> becomes a blank line (except as follows)
                # 2a. <p></p> inside tables are preserved
                # 2b. <p class="*"> gets prepended with "    " per list level for the following class values:
                #     "left"
                #     "code" - also gets wrapped in a <code> tag.
                #     "Caption" - also gets wrapped in ***bolditalic***
                #     "centered"
                #     "SeeItem" - also prepented with a bullet
                # 3. <div*> becomes a blank line NOTE: this kills all divs, including note, tip, etc.
                # 4. <ul*> and <ol*> become a blank line
                # 5. A <li> becomes either "1. " or "#. " depending on if it is inside a ul or li
                # 5a. Also gets prepended with "    " per list level above one, so it is properly nested.
                # NOTE: our CSS might not handle lists more than two levels deep, but this script does.
                # 6. Internal links (no http* at the start) not inside tables are converted to markdown links:
                #   old: <a href="hello/index.html">link text</a>
                #   new: [link text](./hello/index.html) - note no line break after
                # NOTE: this assumes no ./ in front of the links in Flare
                # 7. </h1>-</h4> become two linebreaks
                # 8. </p>,</div>,</ul>,</ol>,</li>,all become a single line break
                # 9. <span> behavior:
                #   class="blue" replaced with <span style="color:blue">
                #   class="red" replaced with <span style="color:red">
                #   if inside a table:
                #       class="b" becomes <b>, class="i" becomes <i>, class="code" becomes <code>
                #   if outside a table:
                #       same as above but with md tags  **b** *i*. class="code" also becomes <code>
                #   All other spans are dropped
                # 10. Everything else is passed through, with all original linebreaks stripped out
                # 11. Nested tags inside an anchor are properly converted.
                #

                # The TODO list: (last modified 5/10/20):
                # * bulleted lists inside tables aren't converted, and end up being random unicode bullet characters with no list form.
                # <span*> tags are dropped, but should be implemented. i.e. <span class="b">foo</span> becomes **foo**
                # * all divs are removed, and there could be a more graceful way of handling that.

                list_stack = []
                newbody = ""
                tmp_guts = ""
                for line in flatbodyarray:
                    # print("tmp_guts: "+tmp_guts)
                    # print("line: "+line)
                    # print(list_stack)
                    # print("   ")
                    if re.search("<[^/][^>]*>",line): # open tag or void tag
                        list_stack.append(line)
                        # do whatever processing for the open/void tag
                        if re.search("<[^/][^>]*/>",line): # void tag such as <br/> or <img/>
                            # TODO also matches <p/> and it's passing those, which might not be right
                            list_stack.pop() # take it back off the list, since there's no close tag
                            tmp_guts += line #TODO: you might want a \n if it's not in a list
                        elif re.search("<h1>",line):
                            tmp_guts += "# "
                        elif re.search("<h2>",line):
                            tmp_guts += "## "
                        elif re.search("<h3>",line):
                            tmp_guts += "### "
                        elif re.search("<h4>",line):
                            tmp_guts += "\n#### "
                        elif re.search("<p[^>]*>",line):
                            if isInElement("<table[^>]*>",list_stack):
                                tmp_guts += line
                            elif re.search("<p class=\"left\">",line):
                                tmp_guts += "\n"
                                tmp_guts += getIndent(list_stack,1)
                            elif re.search("<p class=\"code\">",line):
                                ##TODO:
                                tmp_guts += getIndent(list_stack,1)
                                tmp_guts += "<pre>\n" #if you put a \n before the <pre> it won't be indented
                            elif re.search("<p class=\"codeIndent\">",line):
                                ##TODO: does this need another level of indent?
                                tmp_guts += getIndent(list_stack,1)
                                tmp_guts += "<pre>\n"
                            elif re.search("<p class=\"Caption\">",line):
                                #TODO: this isn't doing anything but indenting
                                #probably should be wrapping it in italics or something
                                tmp_guts += "\n"
                                tmp_guts += getIndent(list_stack,1)
                                tmp_guts += "***"
                            elif re.search("<p class=\"centered\">",line):
                                #TODO: this isn't doing anything but indenting
                                # markdown has no concept of centering, so not sure what to do
                                tmp_guts += "\n"
                                tmp_guts += getIndent(list_stack,1)
                            elif re.search("<p class=\"SeeItem\">",line):
                                #TODO: there's an extra line break between multiple items, would be nice if there wasn't
                                tmp_guts += "\n"
                                tmp_guts += getIndent(list_stack,1)+"* "
                            else: #none of the above. This will eat any classes that aren't implemented above.
                                tmp_guts += "\n"
                        elif re.search("<span[^>]*>",line):
                            #first ones are replaced inside or outside table
                            #these must be replaced with HTMl - no markdown!
                            if re.search("<span class=\"blue\">",line):
                                tmp_guts += "<span style=\"color:blue\">"
                            elif re.search("<span class=\"red\">",line):
                                tmp_guts += "<span style=\"color:red\">"
                            elif isInElement("<table[^>]*>",list_stack):
                                #these tags are transformed inside tables to other HTML. No markdown!
                                if re.search("<span class=\"b\">|<span class=\"function\">",line):
                                    tmp_guts += "<b>"
                                elif re.search("<span class=\"i\"",line):
                                    tmp_guts += "<i>"
                                elif re.search("<span class=\"code\"",line):
                                    tmp_guts += "<code>"
                                else:
                                    tmp_guts += line
                            elif re.search("<span class=\"b\">",line):
                                tmp_guts +="**"
                            elif re.search("<span class=\"i\"",line):
                                tmp_guts +="*"
                            elif re.search("<span class=\"code\"",line):
                                tmp_guts +="<code>"
                            else:
                                pass #eats any other span tags
                        elif re.search("<div[^>]*>",line):
                            tmp_guts += "\n" # WARNING: this eats all divs, including note/tip/etc
                        elif re.search("<ul[^>]*>",line):
                            tmp_guts += "\n"
                        elif re.search("<ol[^>]*>",line):
                            tmp_guts += "\n"
                        elif re.search("<li[^>]*>",line):
                            # determines list depth and adds four spaces per depth-1 before li
                            # i.e. a depth=1 gets no spaces
                            tmp_guts += getIndent(list_stack,0)
                            # determine if this should be ordered or unordered
                            if re.match("<ul[^>]*>",list_stack[-2]):
                                tmp_guts += "* "
                            else:
                                tmp_guts += "1. "
                        elif re.search("<a[^>]*>",line):
                            # keep it on the stack, deal with it at tag close
                            #pass
                            newbody += tmp_guts
                            tmp_guts = ""
                        else: #unimplemented open tag
                            tmp_guts += line #if the open isn't above, just dump it back
                    elif re.search("</[^>]*>",line): #close tag
                #       if #the close tag is the same as the open tag on the top of the stack
                        last_tag = list_stack.pop() #this should be popping the open tag, but it pops the guts for an anchor
                        # do whatever processing for a close tag
                        if re.search("</h\d>",line):
                            tmp_guts += "\n\n"
                        elif re.search("</p>",line):
                            if isInElement("<table[^>]*>",list_stack):
                                tmp_guts += line
                            else:
                                if re.search("<p class=\"code\">",last_tag):
                                    tmp_guts += "\n</pre>\n"
                                if re.search("<p class=\"Caption\">",last_tag):
                                    tmp_guts += "***\n"
                                if re.search("<p class=\"codeIndent\">",last_tag):
                                    tmp_guts += "</pre>\n"
                                else:
                                    tmp_guts += "\n"
                        elif re.search("</span>",line):
                            if re.search("<span class=\"blue\">|<span class=\"red\">",last_tag):
                                tmp_guts += "</span>"
                            elif isInElement("<table[^>]*>",list_stack):
                                if re.search("<span class=\"b\">",last_tag):
                                    tmp_guts += "</b>"
                                elif re.search("<span class=\"i\"",line):
                                    tmp_guts += "</i>"
                                elif re.search("<span class=\"code\"",line):
                                    tmp_guts += "</code>"
                                else:
                                    tmp_guts += line
                            elif re.search("<span class=\"b\">|<span class=\"function\">",last_tag):
                                tmp_guts += "**"
                            elif re.search("<span class=\"i\"",last_tag):
                                tmp_guts +="*"
                            elif re.search("<span class=\"code\"",last_tag):
                                tmp_guts +="</code>"
                            else:
                                pass
                        elif re.search("</div>",line):
                            tmp_guts += "\n"
                        elif re.search("</ul>",line):
                            tmp_guts += "\n"
                        elif re.search("</ol>",line):
                            tmp_guts += "\n"
                        elif re.search("</li>",line):
                            tmp_guts += "\n"
                        elif re.search("</a>",line):
                            #need to deal with a link here
                            # print("making anchors")
                            anchor_guts = tmp_guts
                            anchor_base = last_tag
                            # print("    anchor guts: "+anchor_guts)
                            # print("    anchor base: "+anchor_base)
                            anchor_addr = re.search("href=\"([^\"]*)\"",anchor_base).group(1)
                            #external link
                            if re.search("\"http",anchor_base):
                                tmp_guts = anchor_base+anchor_guts+"</a>"
                            # link in table
                            elif isInElement("<table[^>]*>",list_stack):
                                #NOTE: the reason I did this was concern over not having a ./
                                #at the start of the address. It might work fine without it.
                                #And this could cause problems if a link started with ../
                                #So, keep an eye on this
                                tmp_guts = "<a href=\"./"+anchor_addr+"\">"+anchor_guts+"</a>"
                            else:
                                tmp_guts = "["+anchor_guts+"](./"+anchor_addr+")"
                        elif re.search("</table>",line):
                            tmp_guts += line + "\n"
                        else: # a non-implemented tag
                            tmp_guts += line #if a close tag isn't above, just dump it back
                        # this runs after any close tag
                        if list_stack:
                            if not re.match("<a[^>]*>",list_stack[-1]): #not in an anchor
                                newbody += tmp_guts
                                tmp_guts = ""
                                #print("writing newbody, stack full but no anchor")
                            else:
                                pass #still in an anchor

                        else:
                            #print("stack is empty, writing newline\n\n")
                            newbody += tmp_guts
                            tmp_guts = ""

                    else: #text between tags aka "guts"
                        # need to check if we're in a link or a span and if so, keep the text on the stack
                        # if list_stack:
                        #     if re.match("<a[^>]*>",list_stack[-1]):  # |<span[^>]*> or inside_span:
                        #         list_stack.append(line)
                        #     else:
                        #         newbody += line
                        # else:
                        tmp_guts += line

                #glue yaml lines to start of body string, with linebreaks
                mdout = "---\npageTitle: "+pageTitle+"\nlayout: page-with-toolbar\ndescription: "+description+"\n---\n"+newbody

                # write it back out, but to .md file
                with open(mdfname, "w") as text_file:
                    text_file.write(mdout)
                os.remove(htmlfname)

            #else:
                # If it's anything other than a .html, do nothing.
                #print(fname+" is not html, so it's just copied, no processing")
                # (if there's any other creative pruning we need to do, do it here)
                #TODO: not important, but we could drop *.mclog probably

def isInElement(ele,list_stack):
    """
        Pass this a single element name as a regexp and the stack
        i.e. to find a table pass in "<table[^>]*>"
    """
    isitin = False
    for i in list_stack:
        if re.match(ele,i):
            isitin = True
    return isitin

def getIndent(list_stack,margin):
    """
        pass the stack and margin
        returns spaces for proper indenting (TODO explain what that means)
    """
    # the margin param isn't exactly working
    # 0 = an <li> which adds 4 spaces per depth-1
    # 1 = a pclass which adds 4 spaces per depth
    # but if I pass 2 it should be adding another indent and it isn't
    indentString = ""
    list_depth = margin
    #print(list_stack)
    for i in list_stack:
        if re.match("<ol[^>]*>|<ul[^>]*>",i):
            if list_depth > 0:
                indentString += "    "
            list_depth += 1

    #print(indentString+"hello")
    return indentString

def tagName(fulltag):
    tag = re.search("</*\s*(\w+)",fulltag).group(1)
    return tag

def cleanelement(ele):
    # Do other stuff to make strings yaml-safe
    # Current replacements:
    #   * chop trailing spaces
    #   * \n converted to a space (every element had a \n and eight spaces at the end for some reason)
    #   * ":" converted to a "-"
    #   * &#8482; - convert to nothing
    #   * &#160; - convert to a space
    #   * &#174; - convert to nothing

    s = ET.tostring(ele, method='text').decode("utf-8").rstrip().replace('\n',' ').replace(':','-').replace('&#160;',' ').replace('&#8482;','').replace('&#174;','')
    return s

main()
