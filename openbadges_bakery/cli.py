#! python
import click

from openbadges_bakery import utils


@click.group()
def cli():
    pass


@click.command()
@click.argument('input_file', type=click.File('rb'))
@click.argument('output_file', type=click.File('wb'))
@click.option('--data', type=str, prompt=True)
def bake(input_file, output_file, data):
    """
    This command bakes Open Badges data into a file and saves
    the result to an output file.

    Positional Arguments:

    \b
      Input filename:    File must exist.
    \b
      Output filename:   If file exists, it will be overwritten.
    """
    output = utils.bake(input_file, data, output_file)

    click.echo(
        "{} is done baking. Remember to let it cool".format(output_file.name)
    )


@click.command()
@click.argument('input_file', type=click.File('rb'))
@click.argument('output_file', type=click.File('w'), default='-')
def unbake(input_file, output_file):
    """
    This command extracts Open Badges data from an image and
    prints it to a file or the standard output.

    Positional Arguments:

    \b
      Input filename:    File must exist.
    \b
      Output filename:   If file exists, it will be overwritten.
    """
    assertion_data = utils.unbake(input_file) or ''
    if not assertion_data:
        click.echo('No assertion data found in file.')
    output_file.write(assertion_data)


cli.add_command(bake)
cli.add_command(unbake)

if __name__ == '__main__':
    cli()
