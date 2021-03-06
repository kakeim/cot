#!/usr/bin/env python
#
# xml_file.py - class for reading/editing/writing XML-based data
#
# August 2013, Glenn F. Matthews
# Copyright (c) 2013-2014 the COT project developers.
# See the COPYRIGHT.txt file at the top-level directory of this distribution
# and at https://github.com/glennmatthews/cot/blob/master/COPYRIGHT.txt.
#
# This file is part of the Common OVF Tool (COT) project.
# It is subject to the license terms in the LICENSE.txt file found in the
# top-level directory of this distribution and at
# https://github.com/glennmatthews/cot/blob/master/LICENSE.txt. No part
# of COT, including this file, may be copied, modified, propagated, or
# distributed except according to the terms contained in the LICENSE.txt file.

import xml.etree.ElementTree as ET
import logging
import re

logger = logging.getLogger('cot')

class XML(object):

    @classmethod
    def get_ns(cls, text):
        """Get the namespace prefix from an XML element or attribute name.
        """
        match = re.match(r"\{(.*)\}", str(text))
        if not match:
            logger.error("No namespace prefix on {0}??".format(text))
            return ""
        return match.group(1)


    @classmethod
    def strip_ns(cls, text):
        """Remove the namespace prefix from an XML element or attribute name
        for easier readability"""
        match = re.match(r"\{.*\}(.*)", str(text))
        if match is None:
            logger.error("No namespace prefix on {0}??".format(text))
            return text
        else:
            return match.group(1)


    def read_xml(self, xml_file):
        """Read the given XML file and store it as self.tree / self.root.
        May raise an ET.ParseError.
        """
        # Parse the XML into memory
        self.tree = ET.parse(xml_file)
        self.root = self.tree.getroot()


    def register_namespace(self, prefix, URI):
        ET.register_namespace(prefix, URI)


    def write_xml(self, file):
        """Output the given XML tree to the given file"""
        logger.debug("Writing XML to {0}".format(file))

        # Pretty-print the XML for readability
        self.xml_reindent(self.root, 0)

        # We could make cleaner XML by passing "default_namespace=NSM['ovf']",
        # which will leave off the "ovf:" prefix on elements and attributes in
        # the main OVF namespace, but unfortunately, this cleaner XML is not
        # recognized as valid by ElementTree, resulting in a "write-once" OVF -
        # subsequent attempts to read and re-write the XML will give the error:
        #
        # ValueError: cannot use non-qualified names with default_namespace
        # option
        #
        # This is a bug - see http://bugs.python.org/issue17088
        self.tree.write(file, xml_declaration=True, encoding='utf-8')


    def xml_reindent(self, parent, depth):
        """Recursively add indentation to XML to make it look nice"""
        depth += 2
        last = None
        for elem in list(parent):
            elem.tail = "\n" + (" " * depth)
            self.xml_reindent(elem, depth)
            last = elem

        if last is not None:
            # Parent indents to first child
            parent.text = "\n" + (" " * depth)
            # Last element indents back to parent
            depth -= 2
            last.tail = "\n" + (" " * depth)

        if depth == 0:
            # Add newline at end of file
            parent.tail = "\n"


    @classmethod
    def find_child(cls, parent, tag, children={}, attrib={}, required=False):
        """Find the child element with the given tag and children and/or
        attributes under the specified parent element. Will abort if
        more than one child element matches the given information."""
        matches = cls.find_all_children(parent, tag, children, attrib)
        if len(matches) > 1:
            raise LookupError(
                "Found multiple matching <{0}> children (each with "
                "attributes '{1}' and children '{2}') under "
                "<{3}>:\n{4}"
                        .format(XML.strip_ns(tag), attrib, children,
                                XML.strip_ns(parent.tag),
                                "\n".join([ET.tostring(e) for e in matches])))
        elif len(matches) == 0:
            if required:
                raise KeyError("Mandatory element <{0}> not found under <{1}>"
                               .format(XML.strip_ns(tag),
                                       XML.strip_ns(parent.tag)))
            return None
        else:
            return matches[0]


    @classmethod
    def find_all_children(cls, parent, tag, children={}, attrib={}):
        """Find all child elements with the given tag and children and/or
        attributes under the specified parent element"""
        assert parent is not None
        elements = parent.findall(tag)
        logger.debug("Examining {0} {1} elements under {2}"
                     .format(len(elements), XML.strip_ns(tag),
                             XML.strip_ns(parent.tag)))
        list = []
        for e in elements:
            found = True

            for key in attrib.keys():
                if e.get(key, None) != attrib[key]:
                    logger.debug("Attribute '{0}' ({1}) does not match "
                                 "expected value ({2})"
                                 .format(XML.strip_ns(key), e.get(key, ""),
                                         attrib[key]))
                    found = False
                    break

            if not found:
                continue

            for child_tag in children.keys():
                child = e.find(child_tag)
                if child is None:
                    logger.debug("{0} does not have child {1}"
                                 .format(XML.strip_ns(tag),
                                         XML.strip_ns(child_tag)))
                    found = False
                    break
                if child.text != children[child_tag]:
                    logger.debug("Child '{0}' text ({1}) does not match "
                                 "expected value ({2})"
                                 .format(XML.strip_ns(child_tag),
                                         child.text,
                                         children[child_tag]))
                    found = False
                    break
            if found:
                list.append(e)
        logger.debug("Found {0} matching {1} elements"
                     .format(len(list), XML.strip_ns(tag)))
        return list


    @classmethod
    def add_child(cls, parent, new_child, ordering=None):
        """Add the given child element under the given parent element.
        If ordering is unspecified, the child will be appended after
        all existing children; otherwise, the placement of the child
        relative to other children will respect this ordering.
        """
        if ordering and not (new_child.tag in ordering):
            logger.warning("New child '{0}' is not in the list of "
                           "expected children under '{1}': {2}"
                           .format(tag,
                                   XML.strip_ns(parent.tag),
                                   ordering))
            # Assume this is some sort of custom element, which
            # implicitly goes at the end of the list.
            ordering = None

        if not ordering:
            parent.append(new_child)
        else:
            new_index = ordering.index(new_child.tag)
            i = 0
            found_position = False
            for child in list(parent):
                try:
                    if ordering.index(child.tag) > new_index:
                        found_position = True
                        break
                except ValueError as e:
                    logger.warning("Existing child element '{0}' is not in "
                                   "expected list of children under '{1}': "
                                   "\n{2}"
                                   .format(child.tag,
                                           XML.strip_ns(parent.tag),
                                           ordering))
                    # Assume this is some sort of custom element - all known
                    # elements should implicitly come before it.
                    found_position = True
                    break
                i += 1
            if found_position:
                parent.insert(i, new_child)
            else:
                parent.append(new_child)


    @classmethod
    def set_or_make_child(cls, parent, tag, text=None, attrib=None,
                          ordering=None):
        """Update or create a child element with the desired text
        and/or attributes under the specified parent element.
        The optional 'ordering' parameter is used to provide a list of
        tags for children under the given parent; if a new child element
        is created, its placement will respect this ordering.
        """
        assert parent is not None
        if attrib is None:
            attrib = {}
        element = cls.find_child(parent, tag, attrib=attrib)
        if element is None:
            logger.debug("Creating new {0} under {1}"
                         .format(XML.strip_ns(tag), XML.strip_ns(parent.tag)))
            element = ET.Element(tag)
            XML.add_child(parent, element, ordering)
        if text is not None:
            element.text = str(text)
        for a in attrib:
            element.set(a, attrib[a])
        return element
