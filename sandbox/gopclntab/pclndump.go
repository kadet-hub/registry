// pclndump prints, as one JSON object keyed by file name, what each stripped
// Go ELF binary still says about its build and its code (SEC-18):
//
//	go         the Go release from the build info
//	modules    module path to version: main module, dependencies, replacements
//	funcs      functions with their own code (debug/gosym Table.Funcs)
//	files      source files referenced by any pc-file table (Table.Files)
//	funcnames  every name in the function name table: the functions above
//	           plus the ones that exist only inlined into a caller
//
// Usage: go run pclndump.go <binary>...
package main

import (
	"bytes"
	"debug/buildinfo"
	"debug/elf"
	"debug/gosym"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime/debug"
	"sort"
)

type dump struct {
	Go        string            `json:"go"`
	Modules   map[string]string `json:"modules"`
	Funcs     []string          `json:"funcs"`
	Files     []string          `json:"files"`
	Funcnames []string          `json:"funcnames"`
}

func main() {
	if len(os.Args) < 2 {
		fail(fmt.Errorf("usage: pclndump <binary>..."))
	}
	out := map[string]dump{}
	for _, path := range os.Args[1:] {
		d, err := read(path)
		if err != nil {
			fail(fmt.Errorf("%s: %w", path, err))
		}
		out[filepath.Base(path)] = d
	}
	if err := json.NewEncoder(os.Stdout).Encode(out); err != nil {
		fail(err)
	}
}

func read(path string) (dump, error) {
	bi, err := buildinfo.ReadFile(path)
	if err != nil {
		return dump{}, err
	}
	d := dump{Go: bi.GoVersion, Modules: map[string]string{}}
	add := func(m *debug.Module) {
		if m.Version != "" && m.Version != "(devel)" {
			d.Modules[m.Path] = m.Version
		}
	}
	add(&bi.Main)
	for _, m := range bi.Deps {
		add(m)
		if m.Replace != nil {
			add(m.Replace)
		}
	}

	f, err := elf.Open(path)
	if err != nil {
		return dump{}, err
	}
	defer f.Close()
	sec, text := f.Section(".gopclntab"), f.Section(".text")
	if sec == nil || text == nil {
		return dump{}, fmt.Errorf("no .gopclntab or .text section")
	}
	data, err := sec.Data()
	if err != nil {
		return dump{}, err
	}
	tab, err := gosym.NewTable(nil, gosym.NewLineTable(data, text.Addr))
	if err != nil {
		return dump{}, err
	}
	for _, fn := range tab.Funcs {
		d.Funcs = append(d.Funcs, fn.Name)
	}
	for name := range tab.Files {
		d.Files = append(d.Files, name)
	}

	// pcHeader since Go 1.20 (magic 0xfffffff1): ptrSize at byte 7, then
	// nfunc, nfiles, textStart, funcnameOffset and cuOffset as ptrSize
	// words, so on 64-bit the name table runs from the word at 32 to the one at 40.
	if len(data) < 48 {
		return dump{}, fmt.Errorf("pclntab is %d bytes, shorter than its header", len(data))
	}
	if magic := binary.LittleEndian.Uint32(data); magic != 0xfffffff1 {
		return dump{}, fmt.Errorf("pclntab magic %#x is not the Go 1.20+ layout", magic)
	}
	if data[7] != 8 {
		return dump{}, fmt.Errorf("pointer size %d, only 64-bit binaries are read", data[7])
	}
	start, end := binary.LittleEndian.Uint64(data[32:]), binary.LittleEndian.Uint64(data[40:])
	if start > end || end > uint64(len(data)) {
		return dump{}, fmt.Errorf("function name table %#x..%#x lies outside the %d byte pclntab", start, end, len(data))
	}
	seen := map[string]bool{}
	for _, b := range bytes.Split(data[start:end], []byte{0}) {
		if len(b) > 0 && !seen[string(b)] {
			seen[string(b)] = true
			d.Funcnames = append(d.Funcnames, string(b))
		}
	}
	sort.Strings(d.Funcs)
	sort.Strings(d.Files)
	sort.Strings(d.Funcnames)
	return d, nil
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, "pclndump:", err)
	os.Exit(1)
}
