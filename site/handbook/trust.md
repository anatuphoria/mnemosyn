# Sources and review

Mnemosyn is only useful if you can tell what it is based on and how far to trust it. This page
says where everything comes from, how it is checked, and where its limits are.
{ .lede }

## Where the shapes come from

Every structure is built from a published brain atlas, measured on real MRI scans. Nothing is
drawn by hand. The [Data sources](../atlas/sources.md) page lists each atlas with its authors,
version and licence, and the [Structures](../atlas/structures.md) page shows which source every
structure comes from. In the app, the Info panel names the source of the structure you select,
and **Help, About Mnemosyn** lists all of them.

## Where the texts and models come from

Every description, route step and lesion sign cites numbered references, listed under it in the
Info panel. The Lab's models follow published work: the stress axis after Karin and colleagues
(2020), and water balance after the classic measurements of Robertson and colleagues. In the Lab,
**Model** shows every value with its normal level, range and source, and **What this model
includes** says what each model leaves out.

The experiments in this handbook are checked by tests. Each result a page states is run through
the model by the project's test suite, so a change to a model that would make a page wrong fails
the tests.

## How decisions are made

Every choice about the project, from which atlas to use to how a lesion is counted, is recorded
with its reasons on the [Decisions](../decisions.md) page. The full design behind each part is in
the design documents linked from there.

## The specialist review

Mnemosyn was not built by a neuroanatomy specialist. Its texts are marked **Draft** until a
specialist checks them, and specialists are invited to review the atlas through the
[Review](../review.md) page. Until that review is done, treat everything here as a careful
student's notes: good for understanding, not a final authority.

## The limits

1. No specialist has reviewed it yet.
2. The shapes come from MRI atlases and are less detailed than hand made models.
3. It runs on desktop computers only.
4. There are cranial nerves but no cranial nerve nuclei, so syndromes of the medulla are not
   modelled.
5. The public download has no spinal cord until its authors allow sharing.

Mnemosyn is for studying. It is not for diagnosis or treatment. If you find a mistake, please say
so in the [Discussions](https://github.com/anatuphoria/mnemosyn/discussions); corrections are
welcome.
