# SEC-12 rules for .tf (hcl2) and .tf.json.
package output.terraform

deny contains sprintf("tf-provisioner: %v", [p]) if {
	walk(input, [p, _])
	p[count(p) - 1] in {"local-exec", "remote-exec"}
	"provisioner" in p
}

deny contains "tf-external: data.external" if {
	input.data.external
}
