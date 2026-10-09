# SEC-12 rules for Dockerfile.
package output.dockerfile

deny contains sprintf("dockerfile-remote: ADD %v", [src]) if {
	walk(input, [_, v])
	v.Cmd == "add"
	some src in v.Value
	regex.match(`^(https?|git)://|^git@`, src)
}

deny contains sprintf("dockerfile-remote: RUN %v", [cmd]) if {
	walk(input, [_, v])
	v.Cmd == "run"
	some cmd in v.Value
	regex.match(`\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|da|z|k)?sh\b`, cmd)
}
