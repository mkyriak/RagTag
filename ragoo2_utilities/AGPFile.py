#!/usr/bin/env python
import os
import abc


class AGPFile:

    """
    A class storing the contents of an AGP v2.1 file. https://www.ncbi.nlm.nih.gov/assembly/agp/AGP_Specification/

    The class is able to read new AGP lines in order to sequentially build the complete file.

    At any state, the class should be capable of checking the validity of the file, as well as writing the AGP contents
    to a file stream.

    Common abbreviations:
      "comp": AGP component
      "obj":  AGP object
      "pid":  AGP part number
    """

    def __init__(self, in_file):
        self.agp_version = "v2.1"
        self.fn = os.path.abspath(in_file)

        # Store header and AGP lines separately.
        self.header_lines = []
        self.agp_lines = []

        # Read the contents of the AGP file
        self._read_file()

    @staticmethod
    def _raise_line_err(line_number, message):
        message = "line " + str(line_number) + ": " + message
        raise ValueError(message)

    @staticmethod
    def _is_covered(s):
        s = sorted(s)
        for j in range(1, len(s)):
            if s[j - 1][1] != s[j][0]:
                return False

        return True

    def _read_file(self):
        """
        Read the agp file associated with this instance of the class. If that file doesn't exist yet,
        proceed without reading anything.

        When reading, check the validitiy of individual AGP lines.
        """
        if not os.path.isfile(self.fn):
            return

        # The AGP file exists. Initialize everything.
        self.header_lines = []
        self.agp_lines = []

        line_number = 0
        prev_pid = 0
        in_body = False
        curr_obj = None
        seen_objs = set()
        curr_obj_intervals = []
        with open(self.fn, "r") as f:
            for line in f:
                line_number += 1
                line = line.rstrip()
                if line.startswith("#"):
                    if not in_body:
                        self.header_lines.append(line)
                    else:
                        self._raise_line_err(line_number, "illegal comment in AGP body")
                    continue

                # In a valid AGP file, we should no longer see comment lines
                in_body = True
                fields = line.split("\t")

                # There should be exactly 9 tab delimited fields
                if not len(fields) == 9:
                    self._raise_line_err(line_number, "lines should have 9 tab delimited fields")

                # All fields should have a value
                if not all(fields):
                    self._raise_line_err(line_number, "detected empty field")

                # Instantiate all the AGPLine objects. These will do line-specific validations.
                if fields[4] == "N" or fields[4] == "U":
                    agp_line = AGPGapLine(*fields)
                else:
                    agp_line = AGPSeqLine(*fields)

                self.agp_lines.append(agp_line)

                # Check if we are transitioning object identifiers
                if agp_line.obj != curr_obj:
                    if not agp_line.obj_beg == 1:
                        self._raise_line_err(line_number, "all objects should start with '1'")

                    if agp_line.obj in seen_objs:
                        self._raise_line_err(line_number, "object identifier out of order")

                    # Check that the last object has been completely covered
                    if not self._is_covered(curr_obj_intervals):
                        self._raise_line_err(line_number, "some positions in %s are not accounted for or overlap" % curr_obj)

                    # Update all the info for this new object
                    prev_pid = 0
                    seen_objs.add(agp_line.obj)
                    curr_obj = agp_line.obj
                    curr_obj_intervals = []

                if agp_line.pid - prev_pid != 1:
                    self._raise_line_err(line_number, "non-sequential part_numbers")

                prev_pid = agp_line.pid
                curr_obj_intervals.append((agp_line.obj_beg - 1, agp_line.obj_end))

    def iterate_lines(self):
        """ Iterate over the non-comment lines of AGP file. """
        for i in self.agp_lines:
            yield i


class AGPLine:

    """
    Description
    """

    __metaclass__ = abc.ABCMeta
    allowed_comp_types = set()

    def __init__(self, obj, obj_beg, obj_end, pid, comp_type):
        self.is_gap = None

        # Object info
        self.obj = obj
        self.obj_beg = obj_beg
        self.obj_end = obj_end
        self.pid = pid
        self.comp_type = comp_type

        self._validate_numerics()
        self._validate_obj_coords()
        self._validate_component_type()
        self._validate_line()

    @abc.abstractmethod
    def __str__(self):
        """ Return the tab delimited AGP line"""
        pass

    @abc.abstractmethod
    def _validate_numerics(self):
        """ Ensure all numeric fields and positive integers. """
        pass

    def _validate_obj_coords(self):
        if self.obj_beg > self.obj_end:
            raise ValueError("object_beg (%d) must be <= object_end (%d)" % (self.obj_beg, self.obj_end))

    def _validate_component_type(self):
        if self.comp_type not in self.allowed_comp_types:
            raise ValueError("Invalid component type: %s" % self.comp_type)

    @abc.abstractmethod
    def _validate_line(self):
        """ Final remaining validations specific to the gap or sequence AGP lines. """
        pass


class AGPSeqLine(AGPLine):

    """
    Description
    """

    allowed_comp_types = {"A", "D", "F", "G", "O", "P", "W"}
    allowed_orientations = {"+", "-", "?", "0", "na"}

    def __init__(self, obj, obj_beg, obj_end, pid, comp_type, comp, comp_beg, comp_end, orientation):
        self.comp = comp
        self.comp_beg = comp_beg
        self.comp_end = comp_end
        self.orientation = orientation

        # Set the object attributes and perform superclass-defined validations
        super(AGPSeqLine, self).__init__(obj, obj_beg, obj_end, pid, comp_type)

        self.is_gap = False

    def __str__(self):
        return "\t".join([
            self.obj,
            str(self.obj_beg),
            str(self.obj_end),
            str(self.pid),
            self.comp_type,
            self.comp,
            str(self.comp_beg),
            str(self.comp_end),
            self.orientation
        ])

    def _validate_numerics(self):
        # Convert all numeric types to integers
        try:
            self.obj_beg = int(self.obj_beg)
            self.obj_end = int(self.obj_end)
            self.pid = int(self.pid)
            self.comp_beg = int(self.comp_beg)
            self.comp_end = int(self.comp_end)
        except ValueError:
            raise ValueError("Encountered an invalid non-integer numeric AGP field.")

        # Ensure that all numeric values are positive
        if not all([
            self.obj_beg > 0,
            self.obj_end > 0,
            self.pid > 0,
            self.comp_beg > 0,
            self.comp_end > 0
        ]):
            raise ValueError("Encountered an invalid negative numeric AGP field.")

        # Check the coordinates
        if self.comp_beg > self.comp_end:
            raise ValueError("component_beg (%d) must be <= component_end (%d)" % (self.comp_beg, self.comp_end))

        if self.obj_end - (self.obj_beg-1) != self.comp_end - (self.comp_beg-1):
            raise ValueError("Object coordinates (%d, %d) and component coordinates (%d, %d) do not have the same length" % (self.obj_beg, self.obj_end, self.comp_beg, self.comp_end))

    def _validate_line(self):
        if self.orientation not in AGPSeqLine.allowed_orientations:
            raise ValueError("Invalid orientation: %s" % self.orientation)


class AGPGapLine(AGPLine):

    """
    Description
    """

    allowed_comp_types = {"N", "U"}
    allowed_linkage_types = {"yes", "no"}
    allowed_gap_types = {
        "scaffold", "contig", "centromere", "short_arm", "heterochromatin", "telomere", "repeat", "contamination"
    }
    allowed_evidence_types = {
        "na", "paired-ends", "align_genus", "align_xgenus",
        "align_trnscpt", "within_clone", "clone_contig", "map",
        "pcr", "proximity_ligation", "strobe", "unspecified"
    }

    def __init__(self, obj, obj_beg, obj_end, pid, comp_type, gap_len, gap_type, linkage, linkage_evidence):
        self.gap_len = gap_len
        self.gap_type = gap_type
        self.linkage = linkage
        self.linkage_evidence = linkage_evidence

        # Set the object attributes and perform superclass-defined validations
        super(AGPGapLine, self).__init__(obj, obj_beg, obj_end, pid, comp_type)

        self.is_gap = True

    def __str__(self):
        return "\t".join([
            self.obj,
            str(self.obj_beg),
            str(self.obj_end),
            str(self.pid),
            self.comp_type,
            str(self.gap_len),
            self.gap_type,
            self.linkage,
            self.linkage_evidence
        ])

    def _validate_numerics(self):
        # Convert all numeric types to integers
        try:
            self.obj_beg = int(self.obj_beg)
            self.obj_end = int(self.obj_end)
            self.pid = int(self.pid)
            self.gap_len = int(self.gap_len)
        except ValueError:
            raise ValueError("Encountered an invalid non-integer numeric AGP field.")

        # Ensure that all numeric values are positive
        if not all([
            self.obj_beg > 0,
            self.obj_end > 0,
            self.pid > 0,
            self.gap_len > 0
        ]):
            raise ValueError("Encountered an invalid negative numeric AGP field.")

        # Make sure the coordinates match
        if self.obj_end - (self.obj_beg-1) != self.gap_len:
            raise ValueError("Object coordinates (%d, %d) and gap length (%d) are not the same length." % (self.obj_beg, self.obj_end, self.gap_len))

    def _validate_line(self):
        """ Validation specific to AGP gap lines. """
        if self.comp_type == "U" and self.gap_len != 100:
            raise ValueError("Invalid gap length for component type 'U': %d (should be 100)" % self.gap_len)

        if self.gap_type not in AGPGapLine.allowed_gap_types:
            raise ValueError("Invalid gap type: %s" % self.gap_type)

        if self.linkage not in AGPGapLine.allowed_linkage_types:
            raise ValueError("Invalid linkage field: %s" % self.linkage)

        all_evidence = self.linkage_evidence.split(";")
        for e in all_evidence:
            if e not in AGPGapLine.allowed_evidence_types:
                raise ValueError("Invalid linkage evidence: %s" % e)

        if self.linkage == "no" and self.gap_type == "scaffold":
            raise ValueError("Invalid 'scaffold' gap without linkage evidence")