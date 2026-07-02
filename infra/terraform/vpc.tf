# VPC とサブネット。
# - パブリックサブネット×1: EC2（Elastic IP 経由でインターネット公開）
# - プライベートサブネット×2: RDS（複数 AZ はサブネットグループの必須要件）
# NAT Gateway は使わない（約 $33/月 節約）。RDS は外向き通信不要なので問題なし。

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.project}-vpc"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project}-igw"
  }
}

# --- パブリックサブネット（EC2 用） ---
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidr
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project}-public"
  }
}

# --- プライベートサブネット（RDS 用・2AZ） ---
resource "aws_subnet" "private" {
  count             = length(var.private_subnet_cidrs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "${var.project}-private-${count.index}"
  }
}

# --- ルートテーブル: パブリックは IGW 経由でインターネットへ ---
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# プライベートサブネットは VPC 内ルートのみ（デフォルトルートテーブルを使用）。
# 外向き経路を持たせないことで RDS をインターネットから隔離する。
