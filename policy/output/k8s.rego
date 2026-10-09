# SEC-12 rules for Kubernetes YAML and JSON. Each message starts with the
# capability from policy/manifest.schema.json.
package output.k8s

webhooks := {"ValidatingWebhookConfiguration", "MutatingWebhookConfiguration"}

roles := {"Role", "ClusterRole"}

deny contains sprintf("privileged: %v", [p]) if {
	walk(input, [p, v])
	p[count(p) - 1] == "securityContext"
	v.privileged == true
}

deny contains sprintf("added-capabilities: %v", [p]) if {
	walk(input, [p, v])
	p[count(p) - 1] == "capabilities"
	count(v.add) > 0
}

deny contains sprintf("host-path: %v", [p]) if {
	walk(input, [p, _])
	p[count(p) - 1] == "hostPath"
}

deny contains sprintf("host-namespaces: %v", [array.concat(p, [k])]) if {
	walk(input, [p, v])
	some k in ["hostNetwork", "hostPID", "hostIPC"]
	v[k] == true
}

deny contains sprintf("rbac-admin: %v", [p]) if {
	walk(input, [p, v])
	p[count(p) - 1] == "roleRef"
	v.name == "cluster-admin"
}

deny contains sprintf("rbac-admin: %v", [p]) if {
	walk(input, [p, v])
	v.kind in roles
	some rule in v.rules
	some field in ["verbs", "resources", "apiGroups"]
	"*" in rule[field]
}

deny contains sprintf("admission-webhook: %v", [p]) if {
	walk(input, [p, v])
	v.kind in webhooks
}
