# tcp-eof

A lightweight TCP server that accepts connections and immediately closes them by sending EOF. This is useful as a health check endpoint for load balancers and other monitoring systems.

## What it does

tcp-eof listens on a specified TCP port and immediately closes any incoming connection. This provides a simple way to verify that a service is listening and responsive without requiring any application-level protocol.

## Usage

```bash
tcp-eof <port>
```

Example:
```bash
tcp-eof 9999
```

## Docker

The project includes a minimal Docker image built from scratch:

```bash
docker run ghcr.io/nanonyme/tcp-eof:latest 9999
```

## Use Cases

- **TCP Health Checks for Any Service**: tcp-eof can be used as a health check container for any service, including UDP-based services that need a TCP health check endpoint for load balancer compatibility.
- **Simple TCP Protocol Testing**: Provides a minimal TCP endpoint for testing network connectivity and load balancer configurations.

## AWS ECS Example with ngIRCd

This example demonstrates using tcp-eof as a health check sidecar for an ngIRCd IRC server running on AWS ECS, with a Network Load Balancer providing both direct IRC and TLS-terminated IRC access.

**Why IRC?** IRC is used here as an example of a simple, non-HTTP TCP protocol. This demonstrates why a Network Load Balancer (NLB) is necessary instead of an Application Load Balancer (ALB), which only supports HTTP/HTTPS protocols. The tcp-eof sidecar provides a reliable TCP health check endpoint without requiring implementation of the IRC protocol for health checking.

### Architecture

- **ECS Task**: Runs ngIRCd with tcp-eof as an essential sidecar
- **Network Load Balancer**: 
  - Port 6667: Direct IRC protocol passthrough to ngIRCd
  - Port 6697: TLS termination, forwarding plain IRC to ngIRCd
- **Target Group**: Health checks via TCP connection to tcp-eof sidecar

### CloudFormation Template

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'ngIRCd with tcp-eof health check sidecar on ECS with NLB'

Parameters:
  VpcId:
    Type: AWS::EC2::VPC::Id
    Description: VPC ID where resources will be created
  
  SubnetIds:
    Type: List<AWS::EC2::Subnet::Id>
    Description: List of subnet IDs for the load balancer and ECS service
  
  Certificate:
    Type: String
    Description: ARN of the ACM certificate for TLS termination on port 6697

Resources:
  # ECS Cluster
  ECSCluster:
    Type: AWS::ECS::Cluster
    Properties:
      ClusterName: irc-cluster

  # CloudWatch Logs Group
  LogGroup:
    Type: AWS::CloudWatch::Logs::LogGroup
    Properties:
      LogGroupName: /ecs/ngircd
      RetentionInDays: 7

  # ECS Task Execution Role
  TaskExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Statement:
          - Effect: Allow
            Principal:
              Service: ecs-tasks.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

  # ECS Task Definition
  TaskDefinition:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: ngircd-with-tcp-eof
      NetworkMode: awsvpc
      RequiresCompatibilities:
        - FARGATE
      Cpu: '256'
      Memory: '512'
      ExecutionRoleArn: !GetAtt TaskExecutionRole.Arn
      ContainerDefinitions:
        # ngIRCd IRC server
        - Name: ngircd
          Image: linuxserver/ngircd:latest
          Essential: true
          PortMappings:
            - ContainerPort: 6667
              Protocol: tcp
          Environment:
            - Name: TZ
              Value: UTC
          LogConfiguration:
            LogDriver: awslogs
            Options:
              awslogs-group: !Ref LogGroup
              awslogs-region: !Ref AWS::Region
              awslogs-stream-prefix: ngircd
        
        # tcp-eof sidecar for health checks
        - Name: tcp-eof
          Image: ghcr.io/nanonyme/tcp-eof:latest
          Essential: true
          DependsOn:
            - ContainerName: ngircd
              Condition: START
          Command:
            - '9999'
          PortMappings:
            - ContainerPort: 9999
              Protocol: tcp
          LogConfiguration:
            LogDriver: awslogs
            Options:
              awslogs-group: !Ref LogGroup
              awslogs-region: !Ref AWS::Region
              awslogs-stream-prefix: tcp-eof

  # Security Group for ECS Tasks
  ECSSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: Security group for ngIRCd ECS tasks
      VpcId: !Ref VpcId
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 6667
          ToPort: 6667
          SourceSecurityGroupId: !Ref LoadBalancerSecurityGroup
          Description: IRC from NLB
        - IpProtocol: tcp
          FromPort: 9999
          ToPort: 9999
          SourceSecurityGroupId: !Ref LoadBalancerSecurityGroup
          Description: Health check from NLB

  # Security Group for Network Load Balancer
  LoadBalancerSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: Security group for IRC Network Load Balancer
      VpcId: !Ref VpcId
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 6667
          ToPort: 6667
          CidrIp: 0.0.0.0/0
          Description: IRC plaintext
        - IpProtocol: tcp
          FromPort: 6697
          ToPort: 6697
          CidrIp: 0.0.0.0/0
          Description: IRC with TLS

  # Network Load Balancer
  NetworkLoadBalancer:
    Type: AWS::ElasticLoadBalancingV2::LoadBalancer
    Properties:
      Name: irc-nlb
      Type: network
      Scheme: internet-facing
      Subnets: !Ref SubnetIds
      SecurityGroups:
        - !Ref LoadBalancerSecurityGroup

  # Target Group for IRC with TCP health check on tcp-eof sidecar
  IRCTargetGroup:
    Type: AWS::ElasticLoadBalancingV2::TargetGroup
    Properties:
      Name: irc-targets
      Port: 6667
      Protocol: TCP
      VpcId: !Ref VpcId
      TargetType: ip
      HealthCheckEnabled: true
      HealthCheckProtocol: TCP
      HealthCheckPort: '9999'
      HealthCheckIntervalSeconds: 30
      HealthyThresholdCount: 3
      UnhealthyThresholdCount: 3

  # Listener for plaintext IRC (port 6667)
  PlainTextListener:
    Type: AWS::ElasticLoadBalancingV2::Listener
    Properties:
      LoadBalancerArn: !Ref NetworkLoadBalancer
      Port: 6667
      Protocol: TCP
      DefaultActions:
        - Type: forward
          TargetGroupArn: !Ref IRCTargetGroup

  # Listener for TLS IRC (port 6697) with TLS termination
  TLSListener:
    Type: AWS::ElasticLoadBalancingV2::Listener
    Properties:
      LoadBalancerArn: !Ref NetworkLoadBalancer
      Port: 6697
      Protocol: TLS
      Certificates:
        - CertificateArn: !Ref Certificate
      DefaultActions:
        - Type: forward
          TargetGroupArn: !Ref IRCTargetGroup

  # ECS Service
  ECSService:
    Type: AWS::ECS::Service
    DependsOn:
      - PlainTextListener
      - TLSListener
    Properties:
      ServiceName: ngircd-service
      Cluster: !Ref ECSCluster
      TaskDefinition: !Ref TaskDefinition
      LaunchType: FARGATE
      DesiredCount: 1
      NetworkConfiguration:
        AwsvpcConfiguration:
          AssignPublicIp: ENABLED
          Subnets: !Ref SubnetIds
          SecurityGroups:
            - !Ref ECSSecurityGroup
      LoadBalancers:
        - ContainerName: ngircd
          ContainerPort: 6667
          TargetGroupArn: !Ref IRCTargetGroup

Outputs:
  LoadBalancerDNS:
    Description: DNS name of the Network Load Balancer
    Value: !GetAtt NetworkLoadBalancer.DNSName
  
  PlainTextIRCEndpoint:
    Description: Plaintext IRC endpoint
    Value: !Sub '${NetworkLoadBalancer.DNSName}:6667'
  
  TLSIRCEndpoint:
    Description: TLS IRC endpoint
    Value: !Sub '${NetworkLoadBalancer.DNSName}:6697'
```

### Key Features of the Example

1. **Essential Sidecar Pattern**: Both the tcp-eof and ngIRCd containers are marked as `Essential: true`, ensuring that if either container terminates, ECS will spawn a new task. tcp-eof depends on ngIRCd starting to ensure the IRC server is fully up before the health check begins accepting connections.

2. **TLS Termination**: The NLB listener on port 6697 terminates TLS and forwards plain IRC traffic to ngIRCd on port 6667, allowing ngIRCd to serve both encrypted and unencrypted connections without needing TLS configuration.

3. **TCP Health Checks**: The target group performs TCP health checks on port 9999 (tcp-eof), which immediately closes connections, providing a reliable health indicator without requiring IRC protocol implementation.

4. **Single Target Group**: Both the plaintext (6667) and TLS (6697) listeners forward to the same target group, simplifying the configuration.

## License

See [LICENSE](LICENSE) file for details.
