# ── SPS Shared · dev VPC networking layer ───────────────────────
# Shared platform layer (used by all verticals). VPC 10.0.0.0/16 across
# 2 AZs, three subnet tiers, single NAT (dev cost-saver).

locals {
  # Canonical shared-layer prefix: sps-shared-dev (lowercase-hyphen).
  name_prefix = "sps-shared-${var.environment}"

  # First two AZs in the region (ap-south-1a / ap-south-1b).
  azs = slice(data.aws_availability_zones.available.names, 0, 2)

  public_subnet_cidrs       = ["10.0.0.0/24", "10.0.1.0/24"]   # ALB + NAT
  private_app_subnet_cidrs  = ["10.0.10.0/24", "10.0.11.0/24"] # ECS Fargate
  private_data_subnet_cidrs = ["10.0.20.0/24", "10.0.21.0/24"] # RDS + Redis
}

data "aws_availability_zones" "available" {
  state = "available"
}

# ── VPC ──────────────────────────────────────────────────────────
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name     = "${local.name_prefix}-vpc"
    Vertical = "shared"
  }
}

# ── Internet gateway ─────────────────────────────────────────────
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name     = "${local.name_prefix}-igw"
    Vertical = "shared"
  }
}

# ── Subnets ──────────────────────────────────────────────────────
resource "aws_subnet" "public" {
  count                   = length(local.public_subnet_cidrs)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = local.public_subnet_cidrs[count.index]
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name     = "${local.name_prefix}-public-${count.index + 1}"
    Tier     = "public"
    Vertical = "shared"
  }
}

resource "aws_subnet" "private_app" {
  count             = length(local.private_app_subnet_cidrs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = local.private_app_subnet_cidrs[count.index]
  availability_zone = local.azs[count.index]

  tags = {
    Name     = "${local.name_prefix}-private-app-${count.index + 1}"
    Tier     = "private-app"
    Vertical = "shared"
  }
}

resource "aws_subnet" "private_data" {
  count             = length(local.private_data_subnet_cidrs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = local.private_data_subnet_cidrs[count.index]
  availability_zone = local.azs[count.index]

  tags = {
    Name     = "${local.name_prefix}-private-data-${count.index + 1}"
    Tier     = "private-data"
    Vertical = "shared"
  }
}

# ── NAT gateway (single, dev cost-saver) ─────────────────────────
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name     = "${local.name_prefix}-nat-eip"
    Vertical = "shared"
  }
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id

  tags = {
    Name     = "${local.name_prefix}-nat"
    Vertical = "shared"
  }

  depends_on = [aws_internet_gateway.main]
}

# ── Route tables ─────────────────────────────────────────────────
# Public → IGW
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name     = "${local.name_prefix}-public-rt"
    Tier     = "public"
    Vertical = "shared"
  }
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Private (app + data) → NAT
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }

  tags = {
    Name     = "${local.name_prefix}-private-rt"
    Tier     = "private"
    Vertical = "shared"
  }
}

resource "aws_route_table_association" "private_app" {
  count          = length(aws_subnet.private_app)
  subnet_id      = aws_subnet.private_app[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_data" {
  count          = length(aws_subnet.private_data)
  subnet_id      = aws_subnet.private_data[count.index].id
  route_table_id = aws_route_table.private.id
}
