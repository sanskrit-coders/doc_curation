#!/usr/bin/env python3
# Not working as of 202205
import io
import os
import re
import subprocess
import sys

from tempfile import NamedTemporaryFile
from os import path

objstart = re.compile(b'^\d+ \d+ obj\s*$')

def writebuffer(fh, buffer):
	for line in buffer:
		fh.write(line)

def remove_watermark_objects(infile, outfile, needle):
	'''Searches through infile for needle and removes its innermost containing object.
	Writes to outfile. infile must have been opened in binary mode and outfile must
	have been opened in binary mode.'''
	buffer = False
	foundneedle = False
	for line in infile.readlines():
		# Note that this will only ever strip the innermost object
		# We don't deal with nested objects and so cannot strip an
		# outer object
		if objstart.match(line):
			if buffer:
				writebuffer(outfile, buffer)
			buffer = [line]
		elif line.startswith(b'endobj'):
			if not foundneedle:
				if buffer == False:
					buffer = []
				buffer.append(line)
				writebuffer(outfile, buffer)
			buffer = False
			foundneedle = False
		elif needle in line:
			assert len(buffer) > 5, 'Needle found and we are not in an object'
			foundneedle = True
		elif buffer:
			buffer.append(line)
		else:
			outfile.write(line)

def get_outfilename(infilename):
	if infilename[-4:] == '.pdf':
		return '{}.scrubbed.pdf'.format(infilename[:-4])
	return infilename + '.scrubbed'

if __name__ == '__main__':
	usage = 'Usage: {0} <watermark text> filename [filenames...]\n'.format(sys.argv[0])
	try:
		needle = bytes(sys.argv[1], 'latin-1')
	except IndexError:
		sys.stderr.write(usage)
		sys.exit(1)
	
	if len(sys.argv) < 3:
		sys.stderr.write(usage)
		sys.exit(1)

	for filename in sys.argv[2:]:
		if not path.exists(filename):
			sys.stderr.write('File does not exist: %s\n' % filename)
			sys.exit(2)

		try:
			# 1. Uncompress the file so we can find the watermark text.
			temp1 = NamedTemporaryFile(delete=False)
			temp1.close()
			exitcode = subprocess.call(['pdftk', filename, 'output', temp1.name, 'uncompress'])
			if exitcode != 0:
				sys.stderr.write('pdftk failed to uncompress {}. Aborting.\n'.format(filename))
				sys.exit(3)

			temp2 = NamedTemporaryFile(delete=False)
			remove_watermark_objects(open(temp1.name, 'r+b'), temp2, needle)
			temp2.close()
			
			outfilename = get_outfilename(filename)
			exitcode = subprocess.call(['pdftk', temp2.name, 'output', outfilename, 'compress'])
			if exitcode != 0:
				sys.stderr.write('pdftk failed to compress processed file. Aborting.\n')
				sys.exit(4)

			print('Writing scrubbed file to %s' % outfilename)
		finally:
			try:
				os.unlink(temp1.name)
			except (NameError, OSError):
				pass
			try:
				os.unlink(temp2.name)
			except (NameError, OSError):
				pass
