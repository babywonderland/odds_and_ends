#!/usr/bin/python3
# vi:set noet ts=4 sw=4:
# Tested on Python 3.9.6 for Windows, but probably works on any Python 3

# Created hurriedly for a friend with a ~200GB Excel-style CSV file. It turns
# out that Excel doesn't handle files of such size well. Nor do typical
# editors. So $friend needed it split up into more manageable chunks.
# I don't know how long it took $friend to run this, but in my testing it
# managed a disappointing ~30 min run time per million records. I tried a
# couple random stabs in the dark to improve things and it didn't seem to
# matter much. Didn't pursue further profiling or anything.
import sys
import os
import argparse

def process_args():
	ap_top = argparse.ArgumentParser(
		description="Hacky CSV splitter",
		epilog="(c) 2021 Tait Schaffer, "
			"released into the public domain or "
			"licensed under Creative Commons CC0")
	ap_top.add_argument(
		"-v", "--version",
		action="version",
		version="%(prog)s 0.0.1")
	ap_top.add_argument(
		"input_csv",
		help="Path/filename of input file to scan. Split files are written "
			"to the same directory, named with trailing _1, _2, etc. unless "
			"a different output directory is given with -o.")
	ap_top.add_argument(
		"-n", "--num_per_split",
		type=int, default=100000,
		help="Put this many CSV records in each split file (default: 100k)")
	ap_top.add_argument(
		"-o", "--output-dir",
		help="Save output files (splits of input) to this directory instead "
			"of saving them next to the input file.")
	ap_top.add_argument(
		"-x", "--generate-index",
		help="Write an index to the specified filename of CSV record "
			"number and corresponding byte offset. This can be used to "
			"rapidly find records or further scanning on the file. Writes "
			"an entry for each num_per_split.")
	return ap_top.parse_args()

def next_outfile(input_path, output_dir, counter, width=6):
	outfh = None
	if output_dir:
		(input_dir, input_filename) = os.path.split(input_path)
		(input_fnbase, input_fnext) = os.path.splitext(input_filename)
		initial_output_path = os.path.join(
				output_dir, "{}_{:0{}}{}".format(
					input_fnbase, counter, width, input_fnext))
	else:
		(input_pathbase, input_ext) = os.path.splitext(input_path)
		initial_output_path = "{}_{:0{}}{}".format(
				input_pathbase, counter, width, input_ext)
	output_path = initial_output_path
	retry_count = 0
	while not outfh:
		try:
			# Always create a new output file; never overwrite
			outfh = open(output_path, 'xb')
		except FileExistsError:
			outfh = None
			(output_base, output_ext) = os.path.splitext(initial_output_path)
			retry_count += 1
			output_path = "{}_{}{}".format(
					output_base, retry_count, output_ext)
	return outfh

def run_as_script():
	args = process_args()
	record_num = 0
	output_filenum = 1
	infh = None
	outfh = None
	indexfh = None
	read_size = 1024*1024
	try:
		infh = open(args.input_csv, 'rb', buffering=int(2.5*read_size))
		inbuf = infh.read(read_size)
		if inbuf:
			if args.generate_index:
				indexfh = open(args.generate_index, 'xb')
				# will raise and die here if index file already exists
			outfh = next_outfile(
					args.input_csv, args.output_dir, output_filenum)
			print("Reading... ", end="", flush=True)
		outbuf = bytearray()
		# State machine that tracks Excel-style CSV input where fields may
		# be surrounded with "..." (including newlines within) and literal "s
		# are put within quoted fields using a double-""
		# Newlines are assumed to be either LF or CRLF
		# State tells us when we hit record boundaries so we can count records
		# and split input at legal record boundaries, not in the middle of a
		# record. We don't care about individual fields (delimited with commas)
		# because we can only split at a record boundary, which is a LF
		state = [ "start" ]
		while inbuf:
			for (index, char) in enumerate(inbuf):
				outbuf.append(char)
				if state[-1]=="endquote" and char==ord('"'):
					# Embedded literal " not end of quoted field
					# Excel uses "" to escape " within a quoted field
					# return to inquote state
					state.pop()
					state.append("literal_quote")
				elif state[-1]=="endquote":
					# Prior " was end of quoted field
					state.pop() # endquote
					state.pop() # inquote
				if state[-1]=="literal_quote":
					state.pop()
				elif state[-1]=="inquote" and char==ord('"'):
					state.append("endquote")
				elif state[-1]=="inquote":
					# ignore line breaks and all non-" within quoted fields
					pass
				elif char==ord('"'):
					state.append("inquote")
				elif char==10: # LF
					# at end of a record
					record_num += 1
					if record_num % args.num_per_split == 0:
						if indexfh:
							indexfh.write("{}\t{}\n"
									.format(record_num, infh.tell()-read_size+index+1)
									.encode("ascii"))
						outfh.write(outbuf)
						outbuf = bytearray()
						outfh.flush()
						outfh.close()
						print(".", end="", flush=True)
						output_filenum += 1
						outfh = next_outfile(
								args.input_csv, args.output_dir,
								output_filenum)
			outfh.write(outbuf)
			outbuf = bytearray()
			inbuf = infh.read(read_size)
		# Flush out left-overs
		if outbuf and outbuf[-1] != 10:
			# we didn't end with endrecord state
			record_num += 1
		if outfh:
			outfh.write(outbuf)
		print("\nProcessed {} records into {} files".format(
			record_num, output_filenum))
	finally:
		if infh:
			infh.close()
		if indexfh:
			indexfh.flush()
			indexfh.close()
		if outfh:
			outfh.flush()
			outfh.close()

if __name__ == "__main__":
	run_as_script()

