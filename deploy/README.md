# Deployment preparation — nothing deployed
The image is multi-architecture (amd64/arm64). ECR Terraform, an ECS/Fargate task
skeleton, and a Kubernetes/EKS Deployment/PVC/Service are provided. Placeholders
must be filled deliberately; these are not a production deployment claim.

ECR: review plan, use a remote Terraform state and organization-approved AWS provider
lockfile, build/tag by commit SHA, scan the image, and push only when separately authorized.
ECS: execution role needs ECR/logs/Secrets Manager access; task role needs narrowly scoped
EFS permissions. Pre-create the log group, EFS mount targets, access point UID/GID 10001,
security groups, and TLS load balancer. Service desired count must be one. Disable rolling
overlap (maximumPercent 100, minimumHealthyPercent 0). SQLite/EFS locking and latency
need workload tests before accepting customer production traffic; PostgreSQL is the
preferred migration before production or horizontal scaling.

EKS: provide the EBS CSI driver and a `gp3` StorageClass (WaitForFirstConsumer), provision
`audit-secrets` with SECRET_KEY/ADMIN_PASSWORD/ADMIN_USERNAME, configure TLS ingress,
explicit trusted CSRF origins if needed, egress rules that prohibit internal/metadata
ranges, and database-consistent backups. Recreate strategy and one replica are required
for the SQLite MVP. The shared volume in one pod lets web/worker share database state.
No ingress, public LoadBalancer, cluster creation, paid resources or secrets are created here.

Before cloud launch: test all manifests with your versions, replace SQLite with PostgreSQL
for HA, verify single-worker recovery semantics, add centralized logging, backup/restore
checks, per-customer storage/retention policy, TLS, reset/invitation/account lifecycle and
stronger rate limiting. These checks have NOT been performed against AWS or Kubernetes.
