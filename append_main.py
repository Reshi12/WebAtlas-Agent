import argparse
import yaml

def main():
    parser = argparse.ArgumentParser(description="Autonomous Browser Agent")
    parser.add_argument("task", type=str, help="The task to perform", nargs="?")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config file")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without browser execution")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    if not args.task:
        parser.print_help()
        return
        
    setup_logging(verbose=args.verbose)
    
    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    run_agent(args.task, config, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
